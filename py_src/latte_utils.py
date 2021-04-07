from collections import namedtuple
import asyncio
from adb_utils import run_bash, local_android_file_exists, cat_local_android_file, capture_layout
from a11y_service import A11yServiceManager
LATTE_INTENT = "dev.navids.latte.COMMAND"
FINAL_NAV_FILE = "finish_nav_result.txt"
FINAL_ACITON_FILE = "finish_nav_action.txt"
CUSTOM_STEP_RESULT = "custom_step_result.txt"
ExecutionResult = namedtuple('ExecutionResult', ['state', 'events', 'time', 'resourceId', 'className', 'contentDescription', 'xpath'])


async def send_command_to_latte(command: str, extra: str = "NONE") -> bool:
    extra = extra.replace('"', "__^__").replace(" ", "__^^__").replace(",", "__^^^__")
    bash_cmd = f'adb shell am broadcast -a {LATTE_INTENT} --es command "{command}" --es extra "{extra}"'
    r_code, *_ = await run_bash(bash_cmd)
    return r_code == 0


async def setup_talkback_executor():
    await A11yServiceManager.setup_latte_a11y_services(tb=True)
    await send_command_to_latte("set_step_executor", "talkback")
    await send_command_to_latte("set_delay", "1000")
    await send_command_to_latte("set_physical_touch", "false")
    await send_command_to_latte("enable")


async def setup_sighted_talkback_executor():
    await A11yServiceManager.setup_latte_a11y_services(tb=True)
    await send_command_to_latte("set_step_executor", "sighted_tb")
    await send_command_to_latte("set_delay", "1000")
    await send_command_to_latte("set_physical_touch", "false")
    await send_command_to_latte("enable")


async def setup_regular_executor(physical_touch=True):
    await A11yServiceManager.setup_latte_a11y_services(tb=False)
    await send_command_to_latte("set_step_executor", "regular")
    await send_command_to_latte("set_delay", "1000")
    await send_command_to_latte("set_physical_touch", "true" if physical_touch else "false")
    await send_command_to_latte("enable")


async def talkback_nav_command(command):
    await send_command_to_latte(f"nav_{command}")


async def do_step(json_cmd):
    await send_command_to_latte("do_step", json_cmd)


def is_navigation_done() -> bool:
    return asyncio.run(local_android_file_exists(FINAL_NAV_FILE))


async def tb_navigate_next() -> str:
    print("Perform Next!")
    await A11yServiceManager.setup_latte_a11y_services(tb=True)
    await talkback_nav_command("next")
    next_command_json = await cat_local_android_file(FINAL_ACITON_FILE)
    return next_command_json


async def tb_perform_select() -> (str, str):
    print("Perform Select!")
    await talkback_nav_command("select")
    result = await cat_local_android_file(FINAL_ACITON_FILE)
    layout = await capture_layout()
    return layout, result


def analyze_execution_result(result: str) -> ExecutionResult:
    if not result:
        return ExecutionResult("FAILED", "", "", "", "", "","")
    parts = result.split('$')
    state = parts[1].split(':')[1].strip()
    events = parts[2].split(':')[1].strip()
    time = parts[3].split(':')[1].strip()
    resourceId = parts[4].split('ID=')[1].split(',')[0].strip() if 'ID=' in parts[4] else 'null'
    className = parts[4].split('CL=')[1].split(',')[0].strip() if 'CL=' in parts[4] else 'null'
    contentDescription = parts[4].split('CD=')[1].split(',')[0].strip() if 'CD=' in parts[4] else 'null'
    xpath = parts[4].split('xpath=')[1].strip() if 'xpath=' in parts[4] else ''
    return ExecutionResult(state, events, time, resourceId, className, contentDescription, xpath)


async def execute_command(command: str, executor_name: str = "reg") -> (str, ExecutionResult):
    if executor_name == 'reg':
        await setup_regular_executor()
    elif executor_name == 'tb':
        await setup_talkback_executor()
    elif executor_name == 'stb':
        await setup_sighted_talkback_executor()
    await do_step(command)
    result = await cat_local_android_file(CUSTOM_STEP_RESULT)
    layout_coroutine = asyncio.create_task(capture_layout())
    execution_result = analyze_execution_result(result)
    layout = await layout_coroutine
    return layout, execution_result


async def reg_execute_command(command: str) -> (str, ExecutionResult):
    return await execute_command(command, 'reg')


async def tb_execute_command(command: str) -> (str, ExecutionResult):
    return await execute_command(command, 'tb')


async def stb_execute_command(command: str) -> (str, ExecutionResult):
    return await execute_command(command, 'stb')


def get_missing_actions(a_actions, b_actions, verbose=False):
    a_dict = {}
    b_dict = {}
    for x in a_actions:
        a_dict[x['xpath']] = x
    for x in b_actions:
        b_dict[x['xpath']] = x
    all_keys = set(a_dict.keys()).union(b_dict.keys())
    missing_actions = []
    for k in all_keys:
        if k not in b_dict.keys():
            missing_actions.append(a_dict[k])
        if verbose:
            print(k)
            print("A: ", a_dict.get(k, ""))
            print("B: ", b_dict.get(k, ""))
            print("-----\n")
    return missing_actions
