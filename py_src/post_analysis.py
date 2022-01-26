import pathlib
import json
import argparse
import logging
from snapshot import AddressBook
from latte_utils import ExecutionResult

logger = logging.getLogger(__name__)

POST_ANALYSIS_PREFIX = 'post_analysis_result'

SUCCESS = 10
TB_FAILURE = 5
REG_FAILURE = 4
XML_PROBLEM = 3
UNREACHABLE = 2
DIFFERENT_BEHAVIOR = 0


def old_report_issues(address_book: AddressBook):
    different_behaviors = []
    directional_unreachable = []
    unlocatable = []
    different_behaviors_directional_unreachable = []
    tb_xpaths = {}
    pending = False
    if address_book.snapshot_result_path.joinpath("explore.json").exists():
        with open(address_book.snapshot_result_path.joinpath("explore.json")) as f:
            explore_result = json.load(f)
            for index in explore_result:
                tb_xpaths[explore_result[index]['command']['xpath']] = explore_result[index]['command']
                if not explore_result[index]['same']:
                    different_behaviors.append(explore_result[index]['command'])
    else:
        pending = True

    if address_book.snapshot_result_path.joinpath("stb_result.json").exists():
        with open(address_book.snapshot_result_path.joinpath("stb_result.json")) as f:
            stb_results = json.load(f)
            for key in stb_results:
                e = ExecutionResult(*stb_results[key]['stb_result'])
                if e.state == 'COMPLETED_BY_HELP':
                    unlocatable.append(stb_results[key]['command'])
                elif e.state == 'FAILED' or not stb_results[key]['same']:
                    different_behaviors_directional_unreachable.append(stb_results[key]['command'])
                else:
                    if e.xpath not in tb_xpaths.keys():
                        directional_unreachable.append(stb_results[key]['command'])
    else:
        pending = True
    return different_behaviors, directional_unreachable, unlocatable, \
           different_behaviors_directional_unreachable, pending


def analyze_action(action, address_book: AddressBook, is_sighted: bool) -> dict:
    action_index = action['index']
    prefix = "s_" if is_sighted else ""
    tb_xml_path = address_book.get_layout_path(f'{prefix}tb', action_index)
    reg_xml_path = address_book.get_layout_path(f'{prefix}reg', action_index)
    xml_problem = False
    with open(tb_xml_path, "r") as f:
        tb_xml = f.read()
        if "PROBLEM_WITH_XML" in tb_xml:
            xml_problem = True
    with open(reg_xml_path, "r") as f:
        reg_xml = f.read()
        if "PROBLEM_WITH_XML" in reg_xml:
            xml_problem = True
    issue_status = SUCCESS
    message = "Accessible"
    if "FAILED" in action['tb_action_result'][0]:
        message = "TalkBack Failed"
        issue_status = TB_FAILURE
    elif "FAILED" in action['reg_action_result'][0]:
        message = "Regular Failed"
        issue_status = REG_FAILURE
    elif xml_problem:
        message = "Problem with XML"
        issue_status = XML_PROBLEM
    else:
        if is_sighted:
            if tb_xml == reg_xml:
                message = "Unreachable"
                issue_status = UNREACHABLE
            else:
                message = "Different Behavior"
                issue_status = DIFFERENT_BEHAVIOR
        else:
            if tb_xml != reg_xml:
                message = "Different Behavior"
                issue_status = DIFFERENT_BEHAVIOR

    result = {'index': action_index,
              'issue_status': issue_status,
              'message': message,
              'is_sighted': is_sighted}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot-path', type=str, help="Path of the snapshot's result")
    parser.add_argument('--app-path', type=str, help="Path of the app's result")
    parser.add_argument('--result-path', type=str, help="Path of the result's path")
    parser.add_argument('--name', type=str, required=True, help="Analysis Name")
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--log-path', type=str, help="Path where logs are written")
    args = parser.parse_args()

    available_paths = 0

    if args.snapshot_path:
        available_paths += 1

    if args.app_path:
        available_paths += 1

    if args.result_path:
        available_paths += 1

    if available_paths != 1:
        print(f"Error. You must provide exactly one path to process!")
        exit()

    if args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    if args.log_path:
        logging.basicConfig(level=level,
                            handlers=[
                                logging.FileHandler(args.log_path, mode='w'),
                                logging.StreamHandler()])
    else:
        logging.basicConfig(level=level)

    output_name = f"{POST_ANALYSIS_PREFIX}_{args.name}.jsonl"

    snapshot_paths = []

    if args.result_path:
        result_path = pathlib.Path(args.result_path)
        for app_path in result_path.iterdir():
            if not app_path.is_dir():
                continue
            for snapshot_path in app_path.iterdir():
                if not snapshot_path.is_dir():
                    continue
                snapshot_paths.append(snapshot_path)
    elif args.app_path:
        app_path = pathlib.Path(args.app_path)
        for snapshot_path in app_path.iterdir():
            if not snapshot_path.is_dir():
                continue
            snapshot_paths.append(snapshot_path)
    elif args.snapshot_path:
        snapshot_path = pathlib.Path(args.snapshot_path)
        if not snapshot_path.is_dir():
            print("The snapshot doesn't exist!")
            exit()
        snapshot_paths.append(snapshot_path)

    for snapshot_path in snapshot_paths:

        logger.info(f"Post-analyzing Snapshot in path'{snapshot_path}'...")
        address_book = AddressBook(snapshot_path)

        with open(address_book.snapshot_result_path.joinpath(output_name), 'w') as write_file:
            with open(address_book.action_path) as read_file:
                for line in read_file.readlines():
                    action = json.loads(line)
                    result = analyze_action(action, address_book, is_sighted=False)
                    write_file.write(json.dumps(result) + "\n")
            with open(address_book.s_action_path) as read_file:
                for line in read_file.readlines():
                    action = json.loads(line)
                    result = analyze_action(action, address_book, is_sighted=True)
                    write_file.write(json.dumps(result) + "\n")






