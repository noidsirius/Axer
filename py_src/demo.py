import argparse
import asyncio
import contextlib
import logging
import json
import pathlib
import sys

from ppadb.client_async import ClientAsync as AdbClient
from padb_utils import ParallelADBLogger, save_screenshot
from latte_utils import is_latte_live
from latte_executor_utils import talkback_nav_command, talkback_tree_nodes, latte_capture_layout, \
    FINAL_ACITON_FILE, report_atf_issues, execute_command
from GUI_utils import get_actions_from_layout, get_nodes
from results_utils import OAC, AddressBook
from utils import annotate_elements
from adb_utils import read_local_android_file
from a11y_service import A11yServiceManager
from consts import TB_NAVIGATE_TIMEOUT, DEVICE_NAME, ADB_HOST, ADB_PORT, BLIND_MONKEY_EVENTS_TAG, BLIND_MONKEY_TAG

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def smart__write_open(filename=None):
    if filename and filename != '-':
        fh = open(filename, 'w')
    else:
        fh = sys.stdout

    try:
        yield fh
    finally:
        if fh is not sys.stdout:
            fh.close()


async def execute_latte_command(device, command: str, extra: str):
    padb_logger = ParallelADBLogger(device)
    if command == "tb_a11y_tree":
        windows_info, bm_logs = await talkback_tree_nodes(padb_logger, verbose=True)
        logger.info(f"Windows Info: {json.dumps(windows_info, indent=4)}")
        logger.info(f"Latte Logs: {bm_logs}")
    if command == "capture_layout":
        _, layout = await padb_logger.execute_async_with_log(latte_capture_layout())
        with smart__write_open(extra) as f:
            print(layout, file=f)
    if command == "is_live":
        logger.info(f"Is Latte live? {await is_latte_live()}")
    if command == 'report_atf_issues':
        issues = await report_atf_issues()
        logger.info(f"Reported Issues: {len(issues)}")
        for issue in issues:
            logger.info(f"\tType: {issue['ATFSeverity']} - {issue['ATFType']} - {issue['resourceId']} - {issue['bounds']}")
    if command == "get_actions":  # The extra is the output path
        await save_screenshot(device, extra)
        log_map, layout = await padb_logger.execute_async_with_log(latte_capture_layout())
        if "Problem with XML" in layout:
            logger.error(layout)
            logger.error("Logs: " + log_map)
            return
        actions = get_actions_from_layout(layout)
        annotate_elements(extra, extra, actions, outline=(255, 0, 255), width=15, scale=5)
    if command == "list_CI_elements":
        log_map, layout = await padb_logger.execute_async_with_log(latte_capture_layout())
        if "Problem with XML" in layout:
            logger.error(layout)
            logger.error("Logs: " + log_map)
            return
        ci_elements = get_nodes(layout,
                                filter_query=lambda x: (x.clickable or '16' in x.a11y_actions) and not x.visible)

        logger.info(f"#CI Elements: {len(ci_elements)}")
        for index, element in enumerate(ci_elements):
            logger.info(f"\tCI Elements {index}: {element}")
    if command == "click_CI_element":
        log_map, layout = await padb_logger.execute_async_with_log(latte_capture_layout())
        if "Problem with XML" in layout:
            logger.error(layout)
            logger.error("Logs: " + log_map)
            return
        ci_elements = get_nodes(layout,
                                filter_query=lambda x: (x.clickable or '16' in x.a11y_actions) and not x.visible)
        index = int(extra)
        logger.info(f"Target CI Elements #{index}: {ci_elements[index]}")
        tags = [BLIND_MONKEY_TAG, BLIND_MONKEY_EVENTS_TAG]
        log_message_map, result = await padb_logger.execute_async_with_log(
            execute_command(json.dumps(ci_elements[index]), executor_name='areg'), tags=tags)
        logger.info(f"Result: {result}")
        for tag, value in log_message_map.items():
            logger.info(f"Log --- {tag} --------")
            logger.info(value)

    if command.startswith("nav_"):
        await A11yServiceManager.setup_latte_a11y_services(tb=True)
        await talkback_nav_command(command[len("nav_"):])
        next_command_json = await read_local_android_file(FINAL_ACITON_FILE, wait_time=TB_NAVIGATE_TIMEOUT)
        logger.info(f"Nav Result: '{next_command_json}'")

    if command == "os_rq1":
        result_path = pathlib.Path(extra)
        if not result_path.is_dir():
            logger.error("The result path doesn't exist")
            return
        oac_count = len(OAC)
        header = "\multirow{2}{*}{App} & \multirow{2}{*}{Scenario} & \multirow{2}{*}{\#Nodes} " \
                 + " ".join(f"& \multicolumn{{2}}{{c|}}{{\#{oac_name[:3]}}}" for oac_name in ['All'] + list([oac.name for oac in OAC])) \
                 + "& \multicolumn{2}{c|}{Precision} \\\\" \
                 + "\n" \
                 + f"\cline{{4-{4+(oac_count+2)*2-1}}}" \
                 + "\n" \
                 + "& & {} & Scenario & App \\\\".format("& All & TP " * (oac_count+1)) \
                 + "\n" \
                 +"\hline" \
                 + "\n"
        print(header)
        for app_path in result_path.iterdir():
            if not app_path.is_dir():
                continue

            snapshot_paths = []
            for s_index, snapshot_path in enumerate(app_path.iterdir()):
                if not snapshot_path.is_dir():
                    continue
                snapshot_paths.append(snapshot_path)
            snapshot_count = len(snapshot_paths)
            app_row = "\multirow{" + str(snapshot_count) + "}{*}{" + app_path.name.split('.')[1] + "} "
            s_index = 0
            for snapshot_path in sorted(snapshot_paths, key=lambda x: x.name):
                s_index += 1
                app_row += f"& {s_index} "  # Scenario
                address_book = AddressBook(snapshot_path)
                with open(address_book.get_layout_path("exp", "INITIAL")) as f:
                    number_of_nodes = f.read().count("</node>")
                app_row += f"& {number_of_nodes} "  # Nodes
                for oac in ['oacs'] + list(OAC):
                    number_of_oacs = len(address_book.get_oacs(oac))
                    app_row += f"& {number_of_oacs} & - "
                app_row += "& - &"  # Snapshot Precision
                if s_index == 1:
                    app_row += "\multirow{" + str(snapshot_count) + "}{*}{-} "
                app_row += "\\\\ \n"
            app_row += "\hline \n"
            print(app_row)

    if command == "os_rq2":
        result_path = pathlib.Path(extra)
        if not result_path.is_dir():
            logger.error("The result path doesn't exist")
            return
        header = "App & Scenario & \#Nodes & \#TB Reachable & \#All OA & \#OA TB Reachable & \#TB Actionable & \#API Actionable \\\\ \n"
        header += "\hline \n"
        print(header)
        for app_path in result_path.iterdir():
            if not app_path.is_dir():
                continue

            snapshot_paths = []
            for s_index, snapshot_path in enumerate(app_path.iterdir()):
                if not snapshot_path.is_dir():
                    continue
                snapshot_paths.append(snapshot_path)
            snapshot_count = len(snapshot_paths)
            app_row = "\multirow{" + str(snapshot_count) + "}{*}{" + app_path.name.split('.')[1] + "} "
            s_index = 0
            for snapshot_path in sorted(snapshot_paths, key=lambda x: x.name):
                s_index += 1
                app_row += f"& {s_index} "  # Scenario
                address_book = AddressBook(snapshot_path)
                with open(address_book.get_layout_path("exp", "INITIAL")) as f:
                    number_of_nodes = f.read().count("</node>")
                app_row += f"& {number_of_nodes} "  # Nodes
                tb_reachable_xpaths = set()
                with open(address_book.visited_elements_path) as f:
                    for res in f.readlines():
                        element = json.loads(res)['element']
                        tb_reachable_xpaths.add(element['xpath'])
                app_row += f"& {len(tb_reachable_xpaths)} "  # TB Reachable
                oac_xpaths = set()
                for node in address_book.get_oacs():
                    oac_xpaths.add(node.xpath)
                app_row += f"& {len(oac_xpaths)} "  # OACs
                app_row += f"& {len(oac_xpaths.intersection(tb_reachable_xpaths))} "  # OAC TB Reachable
                tb_actions_xpaths = set()
                api_actions_xpaths = set()
                with open(address_book.action_path) as f:
                    for res in f.readlines():
                        res = json.loads(res)
                        with open(address_book.get_log_path('tb', res['index'], extension=BLIND_MONKEY_EVENTS_TAG)) as f2:
                            if "TYPE_VIEW_CLICKED" in f2.read():
                                tb_actions_xpaths.add(res['element']['xpath'])
                        with open(address_book.get_log_path('areg', res['index'], extension=BLIND_MONKEY_EVENTS_TAG)) as f2:
                            if "TYPE_VIEW_CLICKED" in f2.read():
                                api_actions_xpaths.add(res['element']['xpath'])
                app_row += f"& {len(tb_actions_xpaths)} "  # TB Actions
                app_row += f"& {len(api_actions_xpaths)} "  # API Actions
                app_row += "\\\\ \n"
            app_row += "\hline \n"
            print(app_row)



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--command', type=str, help='The command sending to Latte')
    parser.add_argument('--extra', type=str, default="", help='The extra information sent to Latte')
    parser.add_argument('--device', type=str, default=DEVICE_NAME, help='The device name')
    parser.add_argument('--adb-host', type=str, default=ADB_HOST, help='The host address of ADB')
    parser.add_argument('--adb-port', type=int, default=ADB_PORT, help='The port number of ADB')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    try:
        client = AdbClient(host=args.adb_host, port=args.adb_port)
        device = asyncio.run(client.device(args.device))
        logger.debug(f"Device {device.serial} is connected!")
    except Exception as e:
        logger.error(f"The device is not connected")
        device = None

    if args.command:
        asyncio.run(execute_latte_command(device, args.command, args.extra))
