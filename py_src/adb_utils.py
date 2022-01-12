import logging
import asyncio
import xmlformatter
from typing import Optional


logger = logging.getLogger(__name__)

formatter = xmlformatter.Formatter(indent="1", indent_char="\t", encoding_output="UTF-8", preserve=["literal"])
LATTE_PKG_NAME = "dev.navids.latte"


async def run_bash(cmd) -> (int, str, str):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    return proc.returncode, stdout.decode() if stdout else "", stderr.decode() if stderr else ""


async def capture_layout() -> str:
    cmd = "adb exec-out uiautomator dump /dev/tty"
    _, stdout, _ = await run_bash(cmd)
    layout = stdout.replace("UI hierchary dumped to: /dev/tty", "")
    try:
        layout = formatter.format_string(layout).decode("utf-8")
    except Exception as e:
        logger.error(f"Exception during capturing layout: {e}")
        import random
        layout = f"PROBLEM_WITH_XML {random.random()}"
    return layout


async def load_snapshot(snapshot_name) -> bool:
    cmd = f"adb emu avd snapshot load {snapshot_name}"
    r_code, stdout, stderr = await run_bash(cmd)
    if "OK" not in stdout:
        return False
    r_code, *_ = await run_bash("adb wait-for-device")
    return r_code == 0


async def save_snapshot(snapshot_name) -> None:
    cmd = f"adb emu avd snapshot save {snapshot_name}"
    await run_bash(cmd)


async def get_current_activity_name() -> str:
    cmd = f"adb shell dumpsys window windows  | grep 'mObscuringWindow'"
    r_code, stdout, stderr = await run_bash(cmd)
    return stdout


async def is_android_activity_on_top() -> bool:
    activity_name = await get_current_activity_name()
    android_names = ["com.android.systemui", "com.google.android"]
    for android_name in android_names:
        if android_name in activity_name:
            return True
    return False


async def local_android_file_exists(file_path: str, pkg_name: str = LATTE_PKG_NAME) -> bool:
    cmd = f"adb exec-out run-as {pkg_name} ls files/{file_path}"
    _, stdout, _ = await run_bash(cmd)
    return "No such file or directory" not in stdout


async def cat_local_android_file(file_path: str,
                                 pkg_name: str = LATTE_PKG_NAME,
                                 wait_time: int = -1) -> Optional[str]:
    sleep_time = 1
    index = 0
    while not await local_android_file_exists(file_path):
        if 0 < wait_time < index * sleep_time:
            return None
        index += 1
        logger.debug(f"Waiting for {file_path}")
        await asyncio.sleep(sleep_time)
    cmd = f"adb exec-out run-as {pkg_name} cat files/{file_path}"
    _, stdout, _ = await run_bash(cmd)
    return stdout
