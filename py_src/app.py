import sys
import json
import logging
import subprocess
from collections import defaultdict
import pathlib
import os
import math
import datetime
from flask import Flask, send_from_directory, render_template
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
from snapshot import AddressBook
from post_analysis import POST_ANALYSIS_PREFIX, old_report_issues, SUCCESS, TB_FAILURE, REG_FAILURE, XML_PROBLEM, DIFFERENT_BEHAVIOR, UNREACHABLE

logger = logging.getLogger(__name__)
flask_app = Flask(__name__, static_url_path='', )

# ---------------------------- For Legacy Results ---------------------
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
            snapshot_info['last_update'] = datetime.datetime.fromtimestamp(address_book.snapshot_result_path.stat().st_mtime)
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

@flask_app.route(f'/v2/static/<path:path>')
def send_result_static_v2(path):
    # TODO: Not secure at all
    result_path = pathlib.Path(f"../{path}")
    if not (result_path.exists()):
        return "The path is incorrect!"
    return send_from_directory(result_path.parent.resolve(),result_path.name)


@flask_app.route("/v2/<result_path_str>/")
def report_index_v2(result_path_str: str):
    result_path = pathlib.Path(f"../{result_path_str}")
    if not (result_path.is_dir() and result_path.exists()):
        return "The result path is inccorrect!"
    app_list = defaultdict(list)
    for app_path in result_path.iterdir():
        if not app_path.is_dir():
            continue
        app_name = app_path.name
        app_list[app_name] = []
        for snapshot_path in app_path.iterdir():
            if not snapshot_path.is_dir():
                continue
            snapshot_name = snapshot_path.name
            address_book = AddressBook(snapshot_path)
            snapshot_info = {}
            action_count = 0
            different_behaviors = 0
            unreachable = 0
            other = 0
            analysis_count = 0
            for post_result_path in snapshot_path.iterdir():
                if post_result_path.name.startswith(POST_ANALYSIS_PREFIX):
                    analysis_count += 1
                    with open(str(post_result_path), "r") as f:
                        for line in f.readlines():
                            action_count += 1
                            result = json.loads(line)
                            if result['issue_status'] == XML_PROBLEM:
                                other += 1
                            elif result['issue_status'] == REG_FAILURE:
                                other += 1
                            elif result['issue_status'] == TB_FAILURE:
                                other += 1
                            elif result['issue_status'] == UNREACHABLE:
                                unreachable += 1
                            elif result['issue_status'] == DIFFERENT_BEHAVIOR:
                                different_behaviors += 1
                            elif result['issue_status'] == SUCCESS:
                                continue
                            else:
                                other += 100000

            snapshot_info['id'] = snapshot_name
            snapshot_info['actions'] = "(pending)" if analysis_count == 0 else math.floor(action_count / analysis_count)
            snapshot_info['different_behavior'] = "(pending)" if analysis_count == 0 else math.floor(different_behaviors / analysis_count)
            snapshot_info['unreachable'] = "(pending)" if analysis_count == 0 else math.floor(unreachable / analysis_count)
            snapshot_info['other'] = "(pending)" if analysis_count == 0 else math.floor(other / analysis_count)
            snapshot_info['last_update'] = datetime.datetime.fromtimestamp(address_book.snapshot_result_path.stat().st_mtime)
            app_list[app_name].append(snapshot_info)
        app_list[app_name].sort(key=lambda s: s['last_update'], reverse=True)
    apps = []
    for app in app_list:
        app_info = {}
        app_info['name'] = app.replace(' ', '_')
        app_info['snapshots'] = app_list[app]
        app_info['actions'] = sum(
            [0] + [s['actions'] for s in app_list[app] if str(s['actions']).isdecimal()])
        app_info['different_behavior'] = sum(
            [0] + [s['different_behavior'] for s in app_list[app] if str(s['different_behavior']).isdecimal()])
        app_info['unreachable'] = sum(
            [0] + [s['unreachable'] for s in app_list[app] if str(s['unreachable']).isdecimal()])
        app_info['other'] = sum(
            [0] + [s['other'] for s in app_list[app] if str(s['other']).isdecimal()])
        app_info['last_update'] = max(s['last_update'] for s in app_list[app])
        apps.append(app_info)
    apps.sort(key=lambda a: a['last_update'], reverse=True)
    return render_template('v2_index.html', apps=apps, result_path=result_path_str)


@flask_app.route("/v2/<result_path>/<app_name>/snapshot/<snapshot_name>/diff/<index>/<sighted_str>")
def xml_diff_v2(result_path, app_name, snapshot_name, index, sighted_str):
    is_sighted = sighted_str == "sighted"
    result_path = pathlib.Path(f"../{result_path}")
    if not (result_path.is_dir() and result_path.exists()):
        return "The result path is inccorrect!"
    snapshot_path = result_path.joinpath(app_name).joinpath(snapshot_name)
    flask_app.logger.info(f"Xml Diff for Snapshot_path: {snapshot_path}, index: {index}, is_sighted: {is_sighted}")
    address_book = AddressBook(snapshot_path)
    # xml_name = f"M_{index}.xml" if stb == 'True' else f"{index}.xml"
    prefix = "s_" if is_sighted else ""
    tb_xml_path = address_book.get_layout_path(f'{prefix}tb', index)
    reg_xml_path = address_book.get_layout_path(f'{prefix}reg', index)
    cmd = f"diff --unified {tb_xml_path} {reg_xml_path}"
    diff_string = subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')
    return render_template('xml_diff.html', diff_string=[diff_string])


def create_step(address_book: AddressBook, static_root_path: pathlib.Path, action: dict, post_analysis_results_sub: dict, is_sighted: bool) -> dict:
    prefix = "s_" if is_sighted else ""
    step = {}
    step['index'] = action['index']
    step['action'] = action['element']
    step['init_img'] = address_book.get_screenshot_path(f'{prefix}exp', action['index'], extension='edited').relative_to(static_root_path)
    step['tb_img'] = address_book.get_screenshot_path(f'{prefix}tb', action['index']).relative_to(static_root_path)
    step['reg_img'] = address_book.get_screenshot_path(f'{prefix}reg', action['index']).relative_to(static_root_path)
    step['tb_result'] = action['tb_action_result']
    step['reg_result'] = action['reg_action_result']
    step['is_sighted'] = is_sighted
    step['status'] = min(
        [100] + [post_analysis_results_sub[ana_name][action['index']]['issue_status'] for ana_name in
                post_analysis_results_sub])
    step['status_messages'] = [
        f"{ana_name}: {post_analysis_results_sub[ana_name][action['index']]['message']}" for ana_name in
        post_analysis_results_sub]
    return step

@flask_app.route("/v2/<result_path>/<app_name>/snapshot/<snapshot_name>/report")
def report_v2(result_path, app_name, snapshot_name):
    result_path_str = result_path
    result_path = pathlib.Path(f"../{result_path}")
    if not (result_path.is_dir() and result_path.exists()):
        return "The result path is inccorrect!"
    snapshot_path = result_path.joinpath(app_name).joinpath(snapshot_name)
    address_book = AddressBook(snapshot_path)
    tb_steps = []
    errors = []
    post_analysis_results = {'sighted': {}, 'unsighted': {}}
    for post_result_path in snapshot_path.iterdir():
        if post_result_path.name.startswith(POST_ANALYSIS_PREFIX):
            analysis_name = post_result_path.name[len(POST_ANALYSIS_PREFIX)+1:-len('.jsonl')]
            post_analysis_results['sighted'][analysis_name] = {}
            post_analysis_results['unsighted'][analysis_name] = {}
            with open(str(post_result_path), "r") as f:
                for line in f.readlines():
                    result = json.loads(line)
                    if result['is_sighted']:
                        post_analysis_results['sighted'][analysis_name][result['index']] = result
                    else:
                        post_analysis_results['unsighted'][analysis_name][result['index']] = result
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
            step = create_step(address_book, result_path.parent, action, post_analysis_results['unsighted'], is_sighted=False)
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
            step = create_step(address_book, result_path.parent, action, post_analysis_results['sighted'], is_sighted=True)
            stb_steps.append(step)
    all_steps = {'TalkBack Exploration': tb_steps, 'Sighted TalkBack Checks': stb_steps}
    return render_template('v2_report.html', result_path=result_path_str, app_name=app_name, all_steps=all_steps, name=snapshot_name, errors=errors)