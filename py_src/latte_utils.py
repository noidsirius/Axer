import asyncio
from adb_utils import run_bash, local_android_file_exists, cat_local_android_file, capture_layout
from a11y_service import A11yServiceManager
LATTE_INTENT = "dev.navids.latte.COMMAND"
FINAL_NAV_FILE = "finish_nav_result.txt"
FINAL_ACITON_FILE = "finish_nav_action.txt"

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


async def setup_regular_executor():
    await A11yServiceManager.setup_latte_a11y_services(tb=False)
    await send_command_to_latte("set_step_executor", "regular")
    await send_command_to_latte("set_delay", "1000")
    await send_command_to_latte("set_physical_touch", "true")
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


async def tb_perform_select() -> str:
    print("Perform Select!")
    await talkback_nav_command("select")
    await cat_local_android_file(FINAL_ACITON_FILE)
    layout = await capture_layout()
    return layout


async def reg_perform_select(select_command) -> str:
    print("Now with regular executor")
    await setup_regular_executor()
    # await asyncio.sleep(1)  # TODO: need to change
    await do_step(select_command)
    await asyncio.sleep(1.2)  # TODO: need to change
    layout = await capture_layout()
    return layout


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
        if k not in b_dict:
            missing_actions.append(a_actions[k])
        if verbose:
            print(k)
            print("A: ", a_dict.get(k, ""))
            print("B: ", b_dict.get(k, ""))
            print("-----\n")
    return missing_actions
