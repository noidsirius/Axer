import sys
import json
import logging
import subprocess
from typing import Union
from itertools import cycle
from collections import defaultdict
import pathlib
import os
import math
import datetime
from ansi2html import Ansi2HTMLConverter
from json2html import json2html
from flask import Flask, request, jsonify, send_from_directory, render_template

sys.path.append(str(pathlib.Path(__file__).parent.resolve()))
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
        with open(explore_path, encoding="utf-8") as f:
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
            with open(tb_xml_path, "r", encoding="utf-8") as f:
                tb_xml = f.read()
                if "PROBLEM_WITH_XML" in tb_xml:
                    xml_problem = True
            with open(reg_xml_path, "r", encoding="utf-8") as f:
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
        with open(stb_result_path, encoding="utf-8") as f:
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

def fix_path(path: str) -> str:
    return f"../{path}"


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
            with open(str(post_result_path), "r", encoding="utf-8") as f:
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
    step['action']['detailed_element'] = action.get('detailed_element', 'null')
    step['tags'] = []
    if address_book.tags_path.exists():
        with open(address_book.tags_path, encoding="utf-8") as f:
            for line in f.readlines():
                tag_info = json.loads(line)
                if tag_info['index'] == action['index'] and tag_info['is_sighted'] == is_sighted:
                    step['tags'].append(tag_info['tag'])
    step['mode_info'] = {}

    modes = ['exp', 'tb', 'reg', 'areg']
    step['xml_similar'] = defaultdict(dict)
    for mode in modes:
        for right_mode in modes:
            if right_mode != mode:
                step['xml_similar'][mode][right_mode] = all(action_post_analysis_results[ana_name]['xml_similar_map'][f"{mode}_{right_mode}"] for ana_name in
                                                        action_post_analysis_results)
            else:
                step['xml_similar'][mode][right_mode] = True
        if mode == 'exp':
            step['mode_info'][f'{mode}_img'] = address_book.get_screenshot_path(f'{prefix}{mode}', action['index'],
                                                                                extension='edited').relative_to(
                static_root_path)
            step['mode_info'][f'{mode}_layout'] = address_book.get_layout_path(f'{prefix}{mode}',
                                                                               action['index']).relative_to(
                static_root_path)
            if not is_sighted:
                step['mode_info'][f'{mode}_log'] = address_book.get_log_path(f'{prefix}{mode}',
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
    parent_path = result_path = pathlib.Path(fix_path(""))
    for result_path in parent_path.iterdir():
        if not result_path.is_dir():
            continue
        if result_path.name.endswith("_results"):
            all_result_paths.append(result_path.name)

    def static_path_fixer(path: Union[str, pathlib.Path], result_path: str) -> str:
        if isinstance(path, pathlib.Path):
            path = str(path)
        return path[path.find(result_path):]

    mode_to_repr = defaultdict(lambda: 'UNKOWN',
        {
            'exp': 'Initial',
            'tb': 'TalkBack',
            'reg': 'Touch',
            'areg': 'A11y API'
        })

    return dict(all_result_paths=all_result_paths,
                static_path_fixer=static_path_fixer,
                mode_to_repr=mode_to_repr)


@flask_app.route(f'/v2/static/<path:path>')
def send_result_static_v2(path: str):
    # TODO: Not secure at all
    show_debug = 'debug' in request.args.keys()
    path = pathlib.Path(fix_path(path))
    if not (path.exists()):
        if path.name.endswith(".png"):
            return send_from_directory(fix_path(""), "404.png")
        return "The path is incorrect!"
    if path.name.endswith('.log'):
        with open(path) as f:
            content = ""
            for line in f.readlines():
                if 'DEBUG' not in line or show_debug:
                    content += line
        html_log = Ansi2HTMLConverter().convert(content)
        return html_log
    if path.name.endswith('.jsonl'):
        content_list = []
        with open(path) as f:
            for line in f.readlines():
                content_list.append(json.loads(line))
        return json2html.convert(content_list)

    return send_from_directory(path.parent.resolve(), path.name)


@flask_app.route("/v2/<result_path_str>/")
def report_index_v2(result_path_str: str):
    result_path = pathlib.Path(fix_path(result_path_str))
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
    result_path_str = result_path
    result_path = pathlib.Path(fix_path(result_path))
    if not (result_path.is_dir() and result_path.exists()):
        return "The result path is incorrect!"
    app_result_dir = result_path.joinpath(app_name)
    app = create_app_info(app_result_dir)
    return render_template('v2_app.html', app=app, result_path=result_path_str)


@flask_app.route("/v2/<result_path_str>/search", methods=['GET', 'POST'])
def search_v2(result_path_str: str):
    action_attr_names = ['text', 'contentDescription', 'class', 'resourceId']
    action_attr_fields = []
    for action_attr in action_attr_names:
        action_attr_fields.append(request.args.get(action_attr, None))
    action_xml_attr_names = ['clickable', 'NAF', 'clickableSpan', 'focused', 'focusable', 'enabled']
    action_xml_attr_fields = []
    for action_xml_attr in action_xml_attr_names:
        action_xml_attr_fields.append(request.args.get(action_xml_attr, 'Any'))
    tb_type = request.args.get('tbType', 'both')
    post_analysis_result = request.args.get('postAnalysisResult', 'ANY')
    one_result_per_snapshot = request.args.get('oneResultPerSnapshot', 'off')
    include_tags_field = request.args.get('includeTags', '')
    exclude_tags_field = request.args.get('excludeTags', '')
    app_name_field = request.args.get('appName', 'All')
    tb_result_field = request.args.get('tbResult', 'ALL')
    reg_result_field = request.args.get('regResult', 'ALL')
    areg_result_field = request.args.get('aregResult', 'ALL')
    xml_search_field = request.args.get('xmlSearchQuery', None)
    xml_search_mode = request.args.get('xmlSearchMode', 'ALL')
    xml_search_attr = request.args.get('xmlSearchAttr', 'ALL')
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
    limit_per_snapshot = 1 if one_result_per_snapshot == 'on' else 10000
    include_tags = include_tags_field.split(",")
    exclude_tags = exclude_tags_field.split(",")
    result_path = pathlib.Path(fix_path(result_path_str))
    if not (result_path.is_dir() and result_path.exists()):
        return "The result path is inccorrect!"
    search_query = SearchQuery()\
        .talkback_mode(tb_type) \
        .post_analysis(post_analysis_result=post_analysis_result)\
        .set_valid_app(app_name_field)\

    for action_attr, value in zip(action_attr_names, action_attr_fields):
        if value:
            search_query.contains_action_attr(action_attr, value)

    for action_attr, value in zip(action_xml_attr_names, action_xml_attr_fields):
        if value and value != 'Any':
            search_query.contains_action_xml_attr(action_attr, value)

    if len(include_tags) > 0 or len(exclude_tags) > 0:
        search_query.contains_tags(include_tags, exclude_tags)
    if tb_result_field:
        search_query.executor_result('tb', tb_result_field)
    if reg_result_field:
        search_query.executor_result('reg', reg_result_field)
    if areg_result_field:
        search_query.executor_result('areg', areg_result_field)
    if xml_search_field:
        search_query.xml_search(xml_search_mode, attr=xml_search_attr, query=xml_search_field)

    for (left_xml_field, op_xml_field, right_xml_field) in zip(left_xml_fields, op_xml_fields, right_xml_fields):
        if left_xml_field != 'None' and right_xml_field != 'None':
            search_query.compare_xml(left_xml_field, right_xml_field, should_be_same=op_xml_field == '=')

    search_results = get_search_manager(result_path).search(search_query=search_query,
                                                            # limit=count_field,
                                                            limit_per_snapshot= limit_per_snapshot)
    result_count = len(search_results)
    action_results = []
    for search_result in search_results[:count_field]:
        action_result = create_step(search_result.address_book,
                                    result_path.parent,
                                    search_result.action,
                                    search_result.post_analysis,
                                    is_sighted=search_result.is_sighted)
        action_results.append(action_result)

    app_names = ['All']
    for app_path in result_path.iterdir():
        if not app_path.is_dir():
            continue
        app_names.append(app_path.name)

    return render_template('search.html',
                           result_path=result_path_str,
                           result_count=result_count,
                           action_attrs=zip(action_attr_names, action_attr_fields),
                           action_xml_attrs=zip(action_xml_attr_names, action_xml_attr_fields),
                           tb_type=tb_type,
                           tb_result_field=tb_result_field,
                           reg_result_field=reg_result_field,
                           areg_result_field=areg_result_field,
                           post_analysis_result=post_analysis_result,
                           one_result_per_snapshot=one_result_per_snapshot,
                           count_field=count_field,
                           include_tags_field=include_tags_field,
                           exclude_tags_field=exclude_tags_field,
                           xml_fields=zip(left_xml_fields, cycle(op_xml_fields), right_xml_fields),
                           xml_search_field=xml_search_field,
                           xml_search_mode=xml_search_mode,
                           xml_search_attr=xml_search_attr,
                           action_results=action_results,
                           app_name_field=app_name_field,
                           app_names=app_names)


@flask_app.route("/v2/<result_path>/app/<app_name>/snapshot/<snapshot_name>/action/<index>/<sighted_str>/diff/<left_mode>/<right_mode>")
def xml_diff_v2(result_path, app_name, snapshot_name, index, sighted_str, left_mode, right_mode):
    is_sighted = sighted_str == "sighted"
    result_path = pathlib.Path(fix_path(result_path))
    if not (result_path.is_dir() and result_path.exists()):
        return f"The result path is incorrect! Result Path: {result_path}"
    snapshot_path = result_path.joinpath(app_name).joinpath(snapshot_name)
    flask_app.logger.info(f"Xml Diff for Snapshot_path: {snapshot_path}, index: {index}, is_sighted: {is_sighted}")
    address_book = AddressBook(snapshot_path)
    prefix = "s_" if is_sighted else ""
    left_xml_path = address_book.get_layout_path(f'{prefix}{left_mode}', index)
    right_xml_path = address_book.get_layout_path(f'{prefix}{right_mode}', index)
    cmd = f"diff --unified {left_xml_path} {right_xml_path}"
    diff_string = subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')
    return render_template('xml_diff.html', diff_string=[diff_string])


@flask_app.route("/v2/<result_path>/app/<app_name>/post_analysis")
def post_analysis(result_path, app_name):
    result_path = pathlib.Path(fix_path(result_path)).resolve()
    snapshot_count = do_post_analysis(app_path=pathlib.Path(result_path).joinpath(app_name))
    return jsonify(result=f"{snapshot_count} snapshots of {app_name} are analyzed!")


@flask_app.route("/v2/<result_path>/app/<app_name>/snapshot/<snapshot_name>/action/<index>/<is_sighted>/tag/<tag>")
def tag_action(result_path, app_name, snapshot_name, index, is_sighted, tag):
    result_path = pathlib.Path(fix_path(result_path)).resolve()
    snapshot_path = result_path.joinpath(app_name).joinpath(snapshot_name)
    if not snapshot_path.is_dir():
        return jsonify(result=False)
    if ',' in tag:
        return jsonify(result=False)
    address_book = AddressBook(snapshot_path)
    is_sighted = is_sighted == 'sighted'
    index = int(index)
    with open(address_book.tags_path, 'a', encoding="utf-8") as f:
        f.write(json.dumps({'index': index, 'is_sighted': is_sighted, 'tag': tag}) + "\n")
    return jsonify(result=True)


@flask_app.route("/v2/<result_path>/tags")
def tags_list(result_path):
    result_path_str = result_path
    result_path = pathlib.Path(fix_path(result_path)).resolve()
    if not result_path.is_dir():
        return jsonify(result=False)
    tags = []
    for app_path in result_path.iterdir():
        if not app_path.is_dir():
            continue
        for snapshot_dir in app_path.iterdir():
            if not snapshot_dir.is_dir():
                continue
            address_book = AddressBook(snapshot_dir)
            if not address_book.tags_path.exists():
                continue
            with open(address_book.tags_path, 'r', encoding="utf-8") as f:
                for line in f.readlines():
                    tags.append(json.loads(line)['tag'])
    return render_template('tags.html', result_path=result_path_str, tags=tags)


@flask_app.route("/v2/<result_path>/app/<app_name>/snapshot/<snapshot_name>/report")
def report_v2(result_path, app_name, snapshot_name):
    result_path_str = result_path
    result_path = pathlib.Path(fix_path(result_path))
    if not (result_path.is_dir() and result_path.exists()):
        return "The result path is incorrect!"
    snapshot_path = result_path.joinpath(app_name).joinpath(snapshot_name)
    address_book = AddressBook(snapshot_path)
    tb_steps = []
    errors = []
    error_logs = ""
    with open(f"{str(snapshot_path)}.log", encoding="utf-8") as f:
        for line in f.readlines():
            if line.startswith("ERROR:"):
                error_logs += line
    post_analysis_results = get_post_analysis(snapshot_path=snapshot_path)
    if len(post_analysis_results['unsighted']) == 0:
        errors.append("No post-analysis result is available!")

    if not address_book.action_path.exists():
        errors.append("Explore data doesn't exist!")
    else:
        explore_json = []
        with open(address_book.action_path, encoding="utf-8") as f:
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
        with open(address_book.s_action_path, encoding="utf-8") as f:
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
                           address_book=address_book,
                           error_logs=error_logs,
                           all_steps=all_steps,
                           name=snapshot_name,
                           errors=errors)
