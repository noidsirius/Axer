import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
from snapshot import Snapshot
import json
import subprocess
from collections import defaultdict
import pathlib
import os
import datetime
from flask import Flask, send_from_directory, render_template

app = Flask(__name__, static_url_path='', )

RESULT_STATIC_URI = '/result/'
RESULT_PATH = pathlib.Path("../result")


@app.route(f'{RESULT_STATIC_URI}<path:path>')
def send_result_static(path):
    return send_from_directory(RESULT_PATH, path)


@app.route("/")
def report_index():
    app_list = defaultdict(list)
    for snapshot_result_path in RESULT_PATH.iterdir():
        snapshot_name = snapshot_result_path.name
        if snapshot_result_path.is_dir() and '_' in snapshot_name:
            app_name = ("_".join(snapshot_name.split('_')[:-1])).replace('.','_')
            snapshot = Snapshot(snapshot_name)
            different_behaviors, directional_unreachable\
                , unlocatable, different_behaviors_directional_unreachable, pending = snapshot.report_issues()
            snapshot_info = {}
            snapshot_info['id'] = snapshot_name
            snapshot_info['different_behavior'] = "(pending)" if pending else len(different_behaviors) + len(different_behaviors_directional_unreachable)
            snapshot_info['unreachable'] = "(pending)" if pending else len(unlocatable) + len(directional_unreachable)
            snapshot_info['last_update'] = datetime.datetime.fromtimestamp(snapshot.output_path.stat().st_mtime)
            app_list[app_name].append(snapshot_info)
    apps = []
    for app in app_list:
        app_info = {}
        app_info['name'] = app.replace(' ', '_')
        app_info['snapshots'] = app_list[app]
        app_info['different_behavior'] = "(pending)" if any(True for s in app_list[app] if not str(s['different_behavior']).isdecimal()) else sum(s['different_behavior'] for s in app_list[app])
        app_info['unreachable'] = "(pending)" if any(True for s in app_list[app] if not str(s['unreachable']).isdecimal()) else sum(s['unreachable'] for s in app_list[app] if str(s['unreachable']).isdecimal())
        app_info['last_update'] = max(s['last_update'] for s in app_list[app])
        apps.append(app_info)
    return render_template('index.html', apps=apps)


# @app.route("/snapshot/diff/<name>/<index>", defaults={'stb': 'False'})
@app.route("/snapshot/diff/<name>/<index>")
def xml_diff(name, index):
    explore_path = RESULT_PATH.joinpath(name)
    # xml_name = f"M_{index}.xml" if stb == 'True' else f"{index}.xml"
    xml_name = f"{index}.xml"
    tb_xml_path = explore_path.joinpath("TB").joinpath(xml_name)
    reg_xml_path = explore_path.joinpath("REG").joinpath(xml_name)
    cmd = f"diff --unified {tb_xml_path} {reg_xml_path}"
    diff_string = subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')
    return render_template('xml_diff.html', diff_string=[diff_string])


@app.route("/snapshot/report/<name>")
def report(name):
    explore_path = RESULT_PATH.joinpath(name)
    if not explore_path.exists():
        return f"Snapshot {name} does not exist!"
    with open(explore_path.joinpath("explore.json")) as f:
        explore_json = json.load(f)
    tb_steps = []
    for index in explore_json:
        step = {}
        step['index'] = index
        step['action'] = explore_json[index]['command']
        step['init_img'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("EXP").joinpath(f"{index}_edited.png").absolute(), RESULT_PATH)
        step['tb_img'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("TB").joinpath(f"{index}.png").absolute(),
            RESULT_PATH)
        step['reg_img'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("REG").joinpath(f"{index}.png").absolute(),
            RESULT_PATH)
        step['status'] = explore_json[index]['same']
        step['tb_result'] = explore_json[index]['tb_result']
        step['reg_result'] = explore_json[index]['reg_result']
        tb_steps.append(step)
    with open(explore_path.joinpath("stb_result.json")) as f:
        stb_json = json.load(f)
    stb_steps = []
    for xpath in stb_json:
        step = {}
        index = stb_json[xpath]['index']
        step['index'] = index
        step['action'] = stb_json[xpath]['command']
        step['init_img'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("EXP").joinpath(f"I_{index}_RS.png").absolute(), RESULT_PATH)
        step['tb_img'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("TB").joinpath(f"M_{index}.png").absolute(),
            RESULT_PATH)
        step['reg_img'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("REG").joinpath(f"M_{index}.png").absolute(),
            RESULT_PATH)
        step['status'] = stb_json[xpath].get('same', False)
        step['stb_result'] = stb_json[xpath].get('stb_result', '')
        step['reg_result'] = stb_json[xpath].get('reg_result', '')
        stb_steps.append(step)
    return render_template('report.html', tb_steps=tb_steps, name=name, stb_steps=stb_steps)
