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


@app.route("/snapshot/diff/<name>/<index>")
def xml_diff(name, index):
    explore_path = RESULT_PATH.joinpath(name)
    tb_xml_path = explore_path.joinpath("TB").joinpath(f"{index}.xml")
    reg_xml_path = explore_path.joinpath("REG").joinpath(f"{index}.xml")
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
        step['action'] = explore_json[index]['command']
        step['init_img'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("TB").joinpath(f"{index}.png").absolute(), RESULT_PATH)
        step['tb_img'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("TB").joinpath(f"{index}.png").absolute(),
            RESULT_PATH)
        step['reg_img'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("TB").joinpath(f"{index}.png").absolute(),
            RESULT_PATH)
        step['status'] = explore_json[index]['same']
        step['tb_result'] = explore_json[index]['tb_result']
        step['reg_result'] = explore_json[index]['reg_result']
        step['xml_a'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("TB").joinpath(f"{index}.xml").absolute(),
            RESULT_PATH)
        step['xml_b'] = RESULT_STATIC_URI + os.path.relpath(
            explore_path.joinpath("REG").joinpath(f"{index}.xml").absolute(),
            RESULT_PATH)
        tb_steps.append(step)
    return render_template('report.html', tb_steps=tb_steps, name=name)
