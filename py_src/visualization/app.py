import json
import subprocess
import pathlib
import os
from flask import Flask, send_from_directory, render_template


app = Flask(__name__, static_url_path='', )

RESULT_STATIC_URI = '/result/'
RESULT_PATH = pathlib.Path("../../result")


@app.route(f'{RESULT_STATIC_URI}<path:path>')
def send_result_static(path):
    return send_from_directory(RESULT_PATH, path)


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


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
            explore_path.joinpath("EXP").joinpath(f"{index}.png").absolute(), RESULT_PATH)
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
    print(stb_json)
    stb_steps = []
    for xpath in stb_json:
        step = {}
        index = stb_json[xpath]['index']
        step['index'] = index
        step['action'] = stb_json[xpath]['command']
        step['init_img'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("EXP").joinpath(f"INITIAL.png").absolute(), RESULT_PATH)
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
