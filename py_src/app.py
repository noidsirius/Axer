import sys
import json
import logging
import subprocess
from typing import Union
from collections import defaultdict
import pathlib
import os
import math
import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
from results_utils import AddressBook
from post_analysis import do_post_analysis, get_post_analysis, old_report_issues, SUCCESS, TB_FAILURE, REG_FAILURE, \
    XML_PROBLEM \
    , DIFFERENT_BEHAVIOR, UNREACHABLE, POST_ANALYSIS_PREFIX
from search import get_search_manager, SearchQuery

logger = logging.getLogger(__name__)
flask_app = Flask(__name__, static_url_path='', )

# ---------------------------- For Legacy Results ---------------------
# ---------------------------- TODO: Will Be removed once the old results are analyzed ---------------------
RESULT_STATIC_URI = '/old_result_jan_12/'
RESULT_PATH = pathlib.Path("../old_result_jan_12")


# RESULT_PATH = pathlib.Path("../old_result_jan_12")


@flask_app.route(f'{RESULT_STATIC_URI}<path:path>')
def send_result_static(path):
    return send_from_directory(RESULT_PATH, path)


@flask_app.route("/")
def report_index():
    app_list = defaultdict(list)
    for snapshot_result_path in RESULT_PATH.iterdir():
        snapshot_name = snapshot_result_path.name
        if snapshot_result_path.is_dir() and '_' in snapshot_name:
            app_name = ("_".join(snapshot_name.split('_')[:-1])).replace('.', '_')
            address_book = AddressBook(snapshot_result_path)
            # snapshot = Snapshot(snapshot_name, address_book)
            different_behaviors, directional_unreachable \
                , unlocatable, different_behaviors_directional_unreachable, pending = old_report_issues(address_book)
            snapshot_info = {}
            snapshot_info['id'] = snapshot_name
            snapshot_info['different_behavior'] = "(pending)" if pending else len(different_behaviors) + len(
                different_behaviors_directional_unreachable)
            snapshot_info['unreachable'] = "(pending)" if pending else len(unlocatable) + len(directional_unreachable)
            snapshot_info['last_update'] = datetime.datetime.fromtimestamp(
                address_book.snapshot_result_path.stat().st_mtime)
            app_list[app_name].append(snapshot_info)
    apps = []
    for app in app_list:
        app_info = {}
        app_info['name'] = app.replace(' ', '_')
        app_info['snapshots'] = app_list[app]
        app_info['different_behavior'] = sum(
            [0] + [s['different_behavior'] for s in app_list[app] if str(s['different_behavior']).isdecimal()])
        app_info['unreachable'] = sum(
            [0] + [s['unreachable'] for s in app_list[app] if str(s['unreachable']).isdecimal()])
        app_info['last_update'] = max(s['last_update'] for s in app_list[app])
        apps.append(app_info)
    apps.sort(key=lambda a: a['last_update'], reverse=True)
    return render_template('index.html', apps=apps)


# @app.route("/snapshot/diff/<name>/<index>", defaults={'stb': 'False'})
@flask_app.route("/snapshot/diff/<name>/<index>")
def xml_diff(name, index):
    explore_path = RESULT_PATH.joinpath(name)
    # xml_name = f"M_{index}.xml" if stb == 'True' else f"{index}.xml"
    xml_name = f"{index}.xml"
    tb_xml_path = explore_path.joinpath("TB").joinpath(xml_name)
    reg_xml_path = explore_path.joinpath("REG").joinpath(xml_name)
    cmd = f"diff --unified {tb_xml_path} {reg_xml_path}"
    diff_string = subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')
    return render_template('xml_diff.html', diff_string=[diff_string])


@flask_app.route("/snapshot/report/<name>")
def report(name):
    result_path = RESULT_PATH.joinpath(name)
    if not result_path.exists():
        return f"Snapshot {name} does not exist!"
    explore_path = result_path.joinpath("explore.json")
    tb_steps = []
    errors = []
    if not explore_path.exists():
        errors.append("Explore result doesn't exist!")
    else:
        with open(explore_path) as f:
            explore_json = json.load(f)
        for index in explore_json:
            step = {}
            step['index'] = index
            step['action'] = explore_json[index]['command']
            step['init_img'] = RESULT_STATIC_URI + os.path.relpath(
                result_path.joinpath("EXP").joinpath(f"{index}_edited.png").absolute(), RESULT_PATH)
            step['tb_img'] = RESULT_STATIC_URI + os.path.relpath(
                result_path.joinpath("TB").joinpath(f"{index}.png").absolute(),
                RESULT_PATH)
            step['reg_img'] = RESULT_STATIC_URI + os.path.relpath(
                result_path.joinpath("REG").joinpath(f"{index}.png").absolute(),
                RESULT_PATH)
            step['tb_result'] = explore_json[index]['tb_result']
            step['reg_result'] = explore_json[index]['reg_result']
            xml_name = f"{index}.xml"
            tb_xml_path = result_path.joinpath("TB").joinpath(xml_name)
            reg_xml_path = result_path.joinpath("REG").joinpath(xml_name)
            xml_problem = False
            with open(tb_xml_path, "r") as f:
                tb_xml = f.read()
                if "PROBLEM_WITH_XML" in tb_xml:
                    xml_problem = True
            with open(reg_xml_path, "r") as f:
                reg_xml = f.read()
                if "PROBLEM_WITH_XML" in reg_xml:
                    xml_problem = True
            step['status'] = 1 if (tb_xml == reg_xml) else 0
            step['status_message'] = "Accessible"
            if step['status'] == 0:
                if "FAILED" in step['tb_result'][0]:
                    step['status_message'] = "TalkBack Failed"
                    step['status'] = 2
                elif "FAILED" in step['reg_result'][0]:
                    step['status_message'] = "Regular Failed"
                    step['status'] = 2
                elif xml_problem:
                    step['status_message'] = "Problem with XML"
                    step['status'] = 2
                else:
                    step['status_message'] = "Different Behavior"

            tb_steps.append(step)
    stb_result_path = result_path.joinpath("stb_result.json")
    stb_steps = []
    if not stb_result_path.exists():
        errors.append("Sighted TalkBack result doesn't exist!")
    else:
        with open(stb_result_path) as f:
            stb_json = json.load(f)
        for xpath in stb_json:
            step = {}
            index = stb_json[xpath]['index']
            step['index'] = index
            step['action'] = stb_json[xpath]['command']
            step['init_img'] = RESULT_STATIC_URI + os.path.relpath(
                result_path.joinpath("EXP").joinpath(f"I_{index}_RS.png").absolute(), RESULT_PATH)
            step['tb_img'] = RESULT_STATIC_URI + os.path.relpath(
                result_path.joinpath("TB").joinpath(f"M_{index}.png").absolute(),
                RESULT_PATH)
            step['reg_img'] = RESULT_STATIC_URI + os.path.relpath(
                result_path.joinpath("REG").joinpath(f"M_{index}.png").absolute(),
                RESULT_PATH)
            step['status'] = stb_json[xpath].get('same', False)
            step['stb_result'] = stb_json[xpath].get('stb_result', '')
            step['reg_result'] = stb_json[xpath].get('reg_result', '')
            stb_steps.append(step)
    return render_template('report.html', tb_steps=tb_steps, name=name, stb_steps=stb_steps, errors=errors)


# ---------------------------- End Legacy Results ---------------------


def create_snapshot_info(snapshot_path: pathlib.Path) -> Union[dict, None]:
    if not snapshot_path.is_dir():
        return None
    result_path = snapshot_path.parent.parent
    snapshot_name = snapshot_path.name
    address_book = AddressBook(snapshot_path)
    snapshot_info = {}
    count_map = {
        'actions': 0,
        'different_behavior': 0,
        'unreachable': 0,
        'other': 0,
    }
    analysis_count = 0
    for post_result_path in snapshot_path.iterdir():
        if post_result_path.name.startswith(POST_ANALYSIS_PREFIX):
            analysis_count += 1
            with open(str(post_result_path), "r") as f:
                for line in f.readlines():
                    count_map['actions'] += 1
                    result = json.loads(line)
                    if result['issue_status'] == XML_PROBLEM:
                        count_map['other'] += 1
                    elif result['issue_status'] == REG_FAILURE:
                        count_map['other'] += 1
                    elif result['issue_status'] == TB_FAILURE:
                        count_map['other'] += 1
                    elif result['issue_status'] == UNREACHABLE:
                        count_map['unreachable'] += 1
                    elif result['issue_status'] == DIFFERENT_BEHAVIOR:
                        count_map['different_behavior'] += 1
                    elif result['issue_status'] == SUCCESS:
                        continue
                    else:
                        count_map['other'] += 1000000

    snapshot_info['id'] = snapshot_name
    snapshot_info['log_path'] = str(snapshot_path.relative_to(result_path.parent)) + ".log"
    if analysis_count == 0:
        snapshot_info['state'] = "Pending" if not address_book.finished_path.exists() else "Unprocessed"
        for key in count_map:
            snapshot_info[key] = f"({snapshot_info['state']})"
    else:
        snapshot_info['state'] = "Processed"
        for key in count_map:
            snapshot_info[key] = math.floor(count_map[key] / analysis_count)
    snapshot_info['last_update'] = datetime.datetime.fromtimestamp(address_book.snapshot_result_path.stat().st_mtime)
    return snapshot_info


def create_app_info(app_path: pathlib.Path) -> Union[dict, None]:
    if not app_path.is_dir():
        return None
    app_name = app_path.name
    snapshots_info = []
    for snapshot_path in app_path.iterdir():
        snapshot_info = create_snapshot_info(snapshot_path)
        if snapshot_info is not None:
            snapshots_info.append(snapshot_info)
    snapshots_info.sort(key=lambda s: s['last_update'], reverse=True)
    app_info = {}
    app_info['name'] = app_name.replace(' ', '_')
    app_info['snapshots'] = snapshots_info
    app_info['has_unprocessed'] = any(s['state'] == 'Unprocessed' for s in snapshots_info)
    app_info['actions'] = sum(
        [0] + [s['actions'] for s in snapshots_info if s['state'] == 'Processed'])
    app_info['different_behavior'] = sum(
        [0] + [s['different_behavior'] for s in snapshots_info if s['state'] == 'Processed'])
    app_info['unreachable'] = sum(
        [0] + [s['unreachable'] for s in snapshots_info if s['state'] == 'Processed'])
    app_info['other'] = sum(
        [0] + [s['other'] for s in snapshots_info if s['state'] == 'Processed'])
    app_info['last_update'] = max(s['last_update'] for s in snapshots_info)
    return app_info


def create_step(address_book: AddressBook, static_root_path: pathlib.Path, action: dict,
                action_post_analysis_results: dict, is_sighted: bool) -> dict:
    prefix = "s_" if is_sighted else ""
    step = {}
    step['index'] = action['index']
    step['snapshot_info'] = {
        'result_path': address_book.result_path(),
        'app_name': address_book.app_name(),
        'snapshot_name': address_book.snapshot_name()
    }
    step['action'] = action['element']
    step['tags'] = []
    if address_book.tags_path.exists():
        with open(address_book.tags_path) as f:
            for line in f.readlines():
                tag_info = json.loads(line)
                if tag_info['index'] == action['index'] and tag_info['is_sighted'] == is_sighted:
                    step['tags'].append(tag_info['tag'])
    step['mode_info'] = {}
    modes = ['exp', 'tb', 'reg', 'areg']
    for mode in modes:
        if mode == 'exp':
            step['mode_info'][f'{mode}_img'] = address_book.get_screenshot_path(f'{prefix}{mode}', action['index'],
                                                                                extension='edited').relative_to(
                static_root_path)
            if is_sighted:
                step['mode_info'][f'{mode}_layout'] = address_book.get_layout_path(f'{prefix}{mode}',
                                                                                   "INITIAL").relative_to(
                    static_root_path)
            else:
                step['mode_info'][f'{mode}_log'] = address_book.get_log_path(f'{prefix}{mode}',
                                                                             action['index']).relative_to(
                    static_root_path)
                step['mode_info'][f'{mode}_layout'] = address_book.get_layout_path(f'{prefix}{mode}',
                                                                                   action['index']).relative_to(
                    static_root_path)
        elif f'{mode}_action_result' in action:
            step['mode_info'][f'{mode}_img'] = address_book.get_screenshot_path(f'{prefix}{mode}',
                                                                                action['index']).relative_to(
                static_root_path)
            step['mode_info'][f'{mode}_log'] = address_book.get_log_path(f'{prefix}{mode}',
                                                                         action['index']).relative_to(static_root_path)
            step['mode_info'][f'{mode}_layout'] = address_book.get_layout_path(f'{prefix}{mode}',
                                                                               action['index']).relative_to(
                static_root_path)
            step['mode_info'][f'{mode}_result'] = action[f'{mode}_action_result']
        else:
            step['mode_info'][f'{mode}_img'] = '404.png'
            step['mode_info'][f'{mode}_log'] = None
            step['mode_info'][f'{mode}_layout'] = None
            step['mode_info'][f'{mode}_result'] = None
    step['is_sighted'] = is_sighted
    step['status'] = min(
        [100] + [action_post_analysis_results[ana_name]['issue_status'] for ana_name in
                 action_post_analysis_results])
    step['status_messages'] = [
        f"{ana_name}: {action_post_analysis_results[ana_name]['message']}" for ana_name in
        action_post_analysis_results]
    return step


@flask_app.context_processor
def inject_user():
    all_result_paths = []
    parent_path = result_path = pathlib.Path(f"..")
    for result_path in parent_path.iterdir():
        if not result_path.is_dir():
            continue
        if result_path.name.endswith("_results"):
            all_result_paths.append(result_path.name)
    return dict(all_result_paths=all_result_paths)


@flask_app.route(f'/v2/static/<path:path>')
def send_result_static_v2(path):
    # TODO: Not secure at all
    result_path = pathlib.Path(f"../{path}")
    if not (result_path.exists()):
        if str(result_path).endswith(".png"):
            return send_from_directory("../", "404.png")
        return "The path is incorrect!"
    return send_from_directory(result_path.parent.resolve(), result_path.name)


@flask_app.route("/v2/<result_path_str>/")
def report_index_v2(result_path_str: str):
    result_path = pathlib.Path(f"../{result_path_str}")
    if not (result_path.is_dir() and result_path.exists()):
        return "The result path is inccorrect!"
    apps = []
    for app_path in result_path.iterdir():
        app_info = create_app_info(app_path)
        if app_info is None:
            continue
        apps.append(app_info)
    apps.sort(key=lambda a: a['last_update'], reverse=True)
    return render_template('v2_index.html', apps=apps, result_path=result_path_str)


@flask_app.route("/v2/<result_path>/app/<app_name>")
def report_app_v2(result_path: str, app_name: str):
    result_path = pathlib.Path(f"../{result_path}")
    if not (result_path.is_dir() and result_path.exists()):
        return "The result path is incorrect!"
    app_result_dir = result_path.joinpath(app_name)
    app = create_app_info(app_result_dir)
    return render_template('v2_app.html', app=app, result_path=result_path)


@flask_app.route("/v2/<result_path_str>/search", methods=['GET', 'POST'])
def search_v2(result_path_str: str):
    text_field = request.args.get('text', None)
    content_description_field = request.args.get('contentDescription', None)
    class_name_field = request.args.get('className', None)
    tb_type = request.args.get('tbType', 'both')
    has_post_analysis = request.args.get('hasPostAnalysis', 'off')
    include_tags_field = request.args.get('includeTags', '')
    exclude_tags_field = request.args.get('excludeTags', '')
    tb_result_field = request.args.get('tbResult', 'ALL')
    reg_result_field = request.args.get('regResult', 'ALL')
    areg_result_field = request.args.get('aregResult', 'ALL')
    left_xml_fields = request.args.getlist('leftXML[]')
    op_xml_fields = request.args.getlist('opXML[]')
    right_xml_fields = request.args.getlist('rightXML[]')
    if len(left_xml_fields) == 0:
        left_xml_fields = ['None'] * 2
        op_xml_fields = ['=', '≠']
        right_xml_fields = ['None'] * 2
    count_field = request.args.get('count', '10')
    if not count_field.isdecimal():
        count_field = 10
    count_field = int(count_field)
    include_tags = include_tags_field.split(",")
    exclude_tags = exclude_tags_field.split(",")
    result_path = pathlib.Path(f"../{result_path_str}")
    if not (result_path.is_dir() and result_path.exists()):
        return "The result path is inccorrect!"
    search_query = SearchQuery()\
        .talkback_mode(tb_type) \
        .post_analysis(only_post_analyzed=has_post_analysis == 'on')
    if text_field:
        search_query.contains_text(text_field)
    if content_description_field:
        search_query.contains_content_description(content_description_field)
    if class_name_field:
        search_query.contains_class_name(class_name_field)
    if len(include_tags) > 0 or len(exclude_tags) > 0:
        search_query.contains_tags(include_tags, exclude_tags)
    if tb_result_field:
        search_query.executor_result('tb', tb_result_field)
    if reg_result_field:
        search_query.executor_result('reg', reg_result_field)
    if areg_result_field:
        search_query.executor_result('areg', areg_result_field)

    for (left_xml_field, op_xml_field, right_xml_field) in zip(left_xml_fields, op_xml_fields, right_xml_fields):
        if left_xml_field != 'None' and right_xml_field != 'None':
            search_query.compare_xml(left_xml_field, right_xml_field, should_be_same=op_xml_field == '=')

    search_results = get_search_manager(result_path).search(search_query=search_query,
                                                            limit=count_field)
    action_results = []
    for search_result in search_results:
        action_result = create_step(search_result.address_book,
                                    result_path.parent,
                                    search_result.action,
                                    search_result.post_analysis,
                                    is_sighted=search_result.is_sighted)
        action_results.append(action_result)
    return render_template('search.html',
                           result_path=result_path_str,
                           text_field=text_field,
                           content_description_field=content_description_field,
                           class_name_field=class_name_field,
                           tb_type=tb_type,
                           tb_result_field=tb_result_field,
                           reg_result_field=reg_result_field,
                           areg_result_field=areg_result_field,
                           has_post_analysis=has_post_analysis,
                           count_field=count_field,
                           include_tags_field=include_tags_field,
                           exclude_tags_field=exclude_tags_field,
                           xml_fields=zip(left_xml_fields, op_xml_fields, right_xml_fields),
                           action_results=action_results)


@flask_app.route("/v2/<result_path>/app/<app_name>/snapshot/<snapshot_name>/action/<index>/<sighted_str>/diff")
def xml_diff_v2(result_path, app_name, snapshot_name, index, sighted_str):
    is_sighted = sighted_str == "sighted"
    result_path = pathlib.Path(f"../{result_path}")
    if not (result_path.is_dir() and result_path.exists()):
        return f"The result path is incorrect! Result Path: {result_path}"
    snapshot_path = result_path.joinpath(app_name).joinpath(snapshot_name)
    flask_app.logger.info(f"Xml Diff for Snapshot_path: {snapshot_path}, index: {index}, is_sighted: {is_sighted}")
    address_book = AddressBook(snapshot_path)
    prefix = "s_" if is_sighted else ""
    tb_xml_path = address_book.get_layout_path(f'{prefix}tb', index)
    reg_xml_path = address_book.get_layout_path(f'{prefix}reg', index)
    cmd = f"diff --unified {tb_xml_path} {reg_xml_path}"
    diff_string = subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')
    return render_template('xml_diff.html', diff_string=[diff_string])


@flask_app.route("/v2/<result_path>/app/<app_name>/post_analysis")
def post_analysis(result_path, app_name):
    result_path = pathlib.Path(f"../{result_path}").resolve()
    snapshot_count = do_post_analysis(app_path=pathlib.Path(result_path).joinpath(app_name))
    return jsonify(result=f"{snapshot_count} snapshots of {app_name} are analyzed!")


@flask_app.route("/v2/<result_path>/app/<app_name>/snapshot/<snapshot_name>/action/<index>/<is_sighted>/tag/<tag>")
def tag_action(result_path, app_name, snapshot_name, index, is_sighted, tag):
    result_path = pathlib.Path(f"../{result_path}").resolve()
    snapshot_path = result_path.joinpath(app_name).joinpath(snapshot_name)
    if not snapshot_path.is_dir():
        return jsonify(result=False)
    if ',' in tag:
        return jsonify(result=False)
    address_book = AddressBook(snapshot_path)
    is_sighted = is_sighted == 'sighted'
    index = int(index)
    with open(address_book.tags_path, 'a') as f:
        f.write(json.dumps({'index': index, 'is_sighted': is_sighted, 'tag': tag}) + "\n")
    return jsonify(result=True)


@flask_app.route("/v2/<result_path>/app/<app_name>/snapshot/<snapshot_name>/report")
def report_v2(result_path, app_name, snapshot_name):
    result_path_str = result_path
    result_path = pathlib.Path(f"../{result_path}")
    if not (result_path.is_dir() and result_path.exists()):
        return "The result path is incorrect!"
    snapshot_path = result_path.joinpath(app_name).joinpath(snapshot_name)
    address_book = AddressBook(snapshot_path)
    tb_steps = []
    errors = []
    bm_log_path = str(snapshot_path.relative_to(result_path.parent)) + ".log"
    error_logs = ""
    with open(f"{str(snapshot_path)}.log") as f:
        for line in f.readlines():
            if line.startswith("ERROR:"):
                error_logs += line
    initial_xml_path = str(address_book.get_layout_path('exp', 'INITIAL', ).relative_to(result_path.parent))
    last_explore_log_path = str(address_book.last_explore_log_path.relative_to(result_path.parent))
    all_elements_screenshot = str(address_book.all_element_screenshot.relative_to(result_path.parent))
    all_actions_screenshot = str(address_book.all_action_screenshot.relative_to(result_path.parent))
    visited_actions_in_other_screenshot = str(address_book.redundant_action_screenshot.relative_to(result_path.parent))
    valid_actions_screenshot = str(address_book.valid_action_screenshot.relative_to(result_path.parent))
    visited_actions_screenshot = str(address_book.visited_action_screenshot.relative_to(result_path.parent))
    s_actions_screenshot = str(address_book.s_action_screenshot.relative_to(result_path.parent))
    post_analysis_results = get_post_analysis(snapshot_path=snapshot_path)
    if len(post_analysis_results['unsighted']) == 0:
        errors.append("No post-analysis result is available!")

    if not address_book.action_path.exists():
        errors.append("Explore data doesn't exist!")
    else:
        explore_json = []
        with open(address_book.action_path) as f:
            for line in f.readlines():
                explore_json.append(json.loads(line))
        for action in explore_json:
            step = create_step(address_book, result_path.parent, action,
                               post_analysis_results['unsighted'][action['index']], is_sighted=False)
            tb_steps.append(step)
    stb_steps = []
    if not address_book.s_action_path.exists():
        errors.append("Sighted TalkBack data doesn't exist!")
    else:
        explore_json = []
        with open(address_book.s_action_path) as f:
            for line in f.readlines():
                explore_json.append(json.loads(line))
        for action in explore_json:
            step = create_step(address_book, result_path.parent, action,
                               post_analysis_results['sighted'][action['index']], is_sighted=True)
            stb_steps.append(step)
    all_steps = {'TalkBack Exploration': tb_steps, 'Sighted TalkBack Checks': stb_steps}
    return render_template('v2_report.html',
                           result_path=result_path_str,
                           app_name=app_name,
                           bm_log_path=bm_log_path,
                           error_logs=error_logs,
                           initial_xml_path=initial_xml_path,
                           all_elements_screenshot=all_elements_screenshot,
                           all_actions_screenshot=all_actions_screenshot,
                           visited_actions_in_other_screenshot=visited_actions_in_other_screenshot,
                           visited_actions_screenshot=visited_actions_screenshot,
                           valid_actions_screenshot=valid_actions_screenshot,
                           s_actions_screenshot=s_actions_screenshot,
                           last_explore_log_path=last_explore_log_path,
                           all_steps=all_steps,
                           name=snapshot_name,
                           errors=errors)
