import asyncio
import json
import logging
import random
from typing import List

import xmlformatter

from a11y_service import A11yServiceManager
from adb_utils import read_local_android_file
from consts import LAYOUT_TIMEOUT_TIME, \
    BLIND_MONKEY_TAG, TB_TREELIST_TAG, DEVICE_NAME
from latte_utils import send_command_to_latte
from padb_utils import ParallelADBLogger

logger = logging.getLogger(__name__)

FINAL_ACITON_FILE = "finish_nav_action.txt"
CUSTOM_STEP_RESULT = "custom_step_result.txt"
LAYOUT_FILE_PATH = "a11y_layout.xml"
ATF_ISSUES_FILE_PATH = "aft_a11y_issues.jsonl"
formatter = xmlformatter.Formatter(indent="1", indent_char="\t", encoding_output="UTF-8", preserve=["literal"])

async def latte_capture_layout(device_name: str = DEVICE_NAME) -> str:
    layout = None
    is_tb_enabled = await A11yServiceManager.is_enabled('tb', device_name=device_name)
    for i in range(3):
        logger.debug(f"Capturing layout, Try: {i}")
        await A11yServiceManager.setup_latte_a11y_services(tb=False, device_name=device_name)
        await send_command_to_latte("capture_layout", device_name=device_name)
        layout = await read_local_android_file(LAYOUT_FILE_PATH,
                                               wait_time=LAYOUT_TIMEOUT_TIME,
                                               device_name=device_name)
        if layout:
            break

    if layout is None:
        logger.error(f"Timeout for capturing layout.")
        layout = f"PROBLEM_WITH_XML {random.random()}"

    try:
        layout = formatter.format_string(layout).decode("utf-8")
    except Exception as e:
        logger.error(f"Exception during capturing layout in Latte: {e}")
        layout = f"PROBLEM_WITH_XML {random.random()}"

    if is_tb_enabled:
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=device_name)
    return layout


async def report_atf_issues(device_name: str = DEVICE_NAME) -> List:
    report_jsonl = None
    for i in range(3):
        logger.debug(f"Reporting ATF issues, Try: {i}")
        await A11yServiceManager.enable('latte', device_name=device_name)
        await send_command_to_latte("report_a11y_issues", device_name=device_name)
        report_jsonl = await read_local_android_file(ATF_ISSUES_FILE_PATH,
                                                     wait_time=LAYOUT_TIMEOUT_TIME,
                                                     device_name=device_name)
        if report_jsonl:
            break
    if report_jsonl is None:
        logger.error(f"Timeout for reporting ATF issues.")
        return []
    issues = []
    for line in report_jsonl.split("\n"):
        if line:
            issues.append(json.loads(line))

    return issues


async def talkback_tree_nodes(padb_logger: ParallelADBLogger,
                              verbose: bool = False,
                              device_name: str = DEVICE_NAME) -> (dict, str):
    """
    First enables TalkBack and Latte, then send "tb_a11y_tree" command to Latte, and observes the logs
    from both Latte and TalkBack (which should contains the Virtual View Hierarchy). Finally, returns a
    dictionary from window ids to the window's information and elements inside the window
    :param padb_logger:
    :param verbose: Logs the captured logs from TalkBack
    :param device_name:
    :return: A tuple of WindowInfo and Latte logs. WindowInfo is a map from window id to a map of
    information of window, e.g., title, and its elements. The elements is also a map from element id to
    the element's information such as class name, text, or actions.
    """

    async def send_a11y_tree_command():
        await send_command_to_latte("tb_a11y_tree", device_name=device_name)
        await asyncio.sleep(2)

    # TODO: At the end of this function, the a11y serviecs should be returned to the initial state
    await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=device_name)
    logs, next_command_str = await padb_logger.execute_async_with_log(
        send_a11y_tree_command(),
        tags=[BLIND_MONKEY_TAG, TB_TREELIST_TAG])
    flag = False
    windows_info = {'other': {'info': None, 'elements': {}}}
    for line in logs[TB_TREELIST_TAG].split("\n"):
        if "Node tree traversal order" in line:
            flag = True
            continue
        if not flag:
            continue
        t_line = line[line.index(TB_TREELIST_TAG) + len(TB_TREELIST_TAG):].strip()
        if verbose:
            logger.info(t_line)
        window_tag = "Window: AccessibilityWindowInfo"
        if window_tag in t_line:
            w_line = t_line[t_line.index(window_tag) + len(window_tag):]
            window_attributes = ['title', 'id', 'type', 'bounds', 'focused', 'active']
            w_info = {}
            for attr in window_attributes:
                delimiter = ')' if attr == 'bounds' else ','
                w_info[attr] = w_line[w_line.index(f'{attr}=') + len(f'{attr}='):].split(delimiter)[0]
                if attr == 'bounds':
                    w_info[attr] += ')'
            windows_info[w_info['id']] = {
                'info': w_info,
                'elements': {}
            }
        else:
            # TODO: Replace with regular expression
            e_id = t_line.strip().split(')')[0][1:]
            w_id = t_line.split(')')[1].split('.')[0]
            cls_name = t_line.split('.')[1].split(':')[0]
            bounds = t_line.split(':')[1].split(')')[0] + ')'
            actions = t_line.split(')')[-1][1:].split(':')
            text = '' if ':TEXT{' not in t_line else t_line[t_line.index(':TEXT{') + len(':TEXT{'):].split('}')[0]
            content = '' if ':CONTENT{' not in t_line else \
            t_line[t_line.index(':CONTENT{') + len(':CONTENT{'):].split('}')[0]
            rest = ')'.join(t_line.split(')')[2:-1])
            if text:
                rest = rest.replace(f':TEXT{{{text}}}', '')
            if content:
                rest = rest.replace(f':CONTENT{{{content}}}', '')
            if w_id not in windows_info:
                w_id = 'other'
            windows_info[w_id]['elements'][e_id] = {
                'id': e_id,
                'class_name': cls_name,
                'bounds': bounds,
                'actions': actions,
                'text': text,
                'content': content,
                'rest': rest,
            }

    return windows_info, logs[BLIND_MONKEY_TAG]