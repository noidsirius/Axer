import asyncio

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
    return stdout.replace("UI hierchary dumped to: /dev/tty", "")


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


async def local_android_file_exists(file_path: str, pkg_name: str = LATTE_PKG_NAME) -> bool:
    cmd = f"adb exec-out run-as {pkg_name} ls files/{file_path}"
    _, stdout, _ = await run_bash(cmd)
    return "No such file or directory" not in stdout


async def cat_local_android_file(file_path: str, pkg_name: str = LATTE_PKG_NAME, verbose: bool = False) -> str:
    while not await local_android_file_exists(file_path):
        if verbose:
            print(f"Waiting for {file_path}")
        await asyncio.sleep(1)
    cmd = f"adb exec-out run-as {pkg_name} cat files/{file_path}"
    _, stdout, _ = await run_bash(cmd)
    return stdout
