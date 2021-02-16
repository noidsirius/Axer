import asyncio
from adb_utils import run_bash, local_android_file_exists
from a11y_service import A11yServiceManager
LATTE_INTENT = "dev.navids.latte.COMMAND"
FINAL_NAV_FILE = "finish_nav_result.txt"


async def send_command_to_latte(command: str, extra: str = "NONE") -> bool:
    extra = extra.replace('"', "__^__").replace(" ", "__^^__").replace(",", "__^^^__")
    bash_cmd = f'adb shell am broadcast -a {LATTE_INTENT} --es command "{command}" --es extra "{extra}"'
    r_code, *_ = await run_bash(bash_cmd)
    return r_code == 0


async def setup_talkback_executor():
    await A11yServiceManager.setup_latte_a11y_services(tb=True)
    await send_command_to_latte("set_step_executor", "talkback")
    await send_command_to_latte("set_delay", "2000")
    await send_command_to_latte("set_physical_touch", "false")
    await send_command_to_latte("enable")


async def setup_regular_executor():
    await A11yServiceManager.setup_latte_a11y_services(tb=False)
    await send_command_to_latte("set_step_executor", "regular")
    await send_command_to_latte("set_delay", "2000")
    await send_command_to_latte("set_physical_touch", "true")
    await send_command_to_latte("enable")


async def talkback_nav_command(command):
    await send_command_to_latte(f"nav_{command}")


async def do_step(json_cmd):
    await send_command_to_latte("do_step", json_cmd)


def is_navigation_done() -> bool:
    return asyncio.run(local_android_file_exists(FINAL_NAV_FILE))
