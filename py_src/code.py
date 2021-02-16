import sys
import shutil
import asyncio
import aiofiles
from typing import Any, List
from pathlib import Path
import json
from lxml import etree
from ppadb.client_async import ClientAsync as AdbClient
# from ppadb.client import Client as AdbClient

LATTE_PKG_NAME = "dev.navids.latte"
LATTE_INTENT = "dev.navids.latte.COMMAND"
FINAL_NAV_FILE = "finish_nav_result.txt"
FINAL_ACITON_FILE = "finish_nav_action.txt"

async def run_bash(cmd) -> (int, str, str):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    return proc.returncode, stdout.decode() if stdout else "", stderr.decode() if stderr else ""


async def save_screenshot(device, file_name) -> None:
    result = await device.screencap()
    # result = device.screencap()
    print("A")
    await asyncio.sleep(2)
    print("B")
    async with aiofiles.open(file_name, mode='wb') as f:
        await asyncio.sleep(2)
        print("C")
        await f.write(result)
    print("D")
    await asyncio.sleep(2)
    print("E")
    return file_name


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


async def send_command_to_latte(command: str, extra: str = "NONE") -> bool:
    extra = extra.replace('"', "__^__").replace(" ", "__^^__").replace(",", "__^^^__")
    bash_cmd = f'adb shell am broadcast -a {LATTE_INTENT} --es command "{command}" --es extra "{extra}"'
    r_code, *_ = await run_bash(bash_cmd)
    return r_code == 0

def get_element(node):
    # for XPATH we have to count only for nodes with same type!
    length = 0
    index = -1
    if node.getparent() is not None:
        for x in node.getparent().getchildren():
            if node.attrib.get('class', 'NONE1') == x.attrib.get('class', 'NONE2'):
                length += 1
            if x == node:
                index = length
    if length > 1:
        return f"{node.attrib.get('class', '')}[{index}]"
    return node.attrib.get('class', '')


def get_xpath(node):
    node_class_name = get_element(node)
    path = '/' + node_class_name if node_class_name != "" else ""
    if node.getparent() is not None and node.getparent().attrib.get('class', 'NONE') != 'hierarchy':
        path = get_xpath(node.getparent()) + path
    return path


class A11yServiceManager:
    services = {"tb": "com.google.android.marvin.talkback/com.google.android.marvin.talkback.TalkBackService",
                         "latte": "dev.navids.latte/dev.navids.latte.app.MyLatteService"}

    @staticmethod
    async def get_enabled_services() -> List[str]:
        _, enabled_services, _ = await run_bash("adb shell settings get secure enabled_accessibility_services")
        if 'null' in enabled_services:
            return []
        return enabled_services.strip().split(':')

    @staticmethod
    async def is_enabled(service_name: str) -> bool:
        if service_name not in A11yServiceManager.services:
            return False
        enabled_services = await A11yServiceManager.get_enabled_services()
        return A11yServiceManager.services[service_name] in enabled_services

    @staticmethod
    async def enable(service_name: str) -> bool:
        if service_name not in A11yServiceManager.services:
            return False
        enabled_services = await A11yServiceManager.get_enabled_services()
        if A11yServiceManager.services[service_name] in enabled_services:
            return True
        enabled_services_str = ":".join(enabled_services + [A11yServiceManager.services[service_name]])
        r_code, *_ = await run_bash(
            f"adb shell settings put secure enabled_accessibility_services {enabled_services_str}")
        return r_code == 0

    @staticmethod
    async def disable(service_name: str) -> bool:
        if service_name not in A11yServiceManager.services:
            return False
        enabled_services = await A11yServiceManager.get_enabled_services()
        if A11yServiceManager.services[service_name] not in enabled_services:
            return True
        enabled_services.remove(A11yServiceManager.services[service_name])
        enabled_services_str = ":".join(enabled_services)
        if len(enabled_services_str) == 0:
            r_code, *_ = await run_bash(
                f"adb shell settings delete secure enabled_accessibility_services")
        else:
            r_code, *_ = await run_bash(
                f"adb shell settings put secure enabled_accessibility_services {enabled_services_str}")
        return r_code == 0


class ParallelADBLogger:
    def __init__(self, device):
        self.device = device
        self.lock = None
        self.log_message = ""

    async def _logcat(self):
        async def logcat_handler(connection):
            global log_list
            while True:
                data = await connection.read(1024)
                if not data:
                    break
                self.log_message += data.decode('utf-8')
            await connection.close()
        conn = await self.device.create_connection(timeout=None)
        cmd = "shell:{}".format("logcat -c; logcat")
        await conn.send(cmd)
        await logcat_handler(conn)

    async def execute_async_with_log(self, coroutine_obj: asyncio.coroutine) -> (str, Any):
        if self.lock is not None:
            raise Exception("Cannot execute more than one coroutine while logging!")
        self.lock = coroutine_obj
        self.log_message = ""
        ll_task = asyncio.create_task(self._logcat())
        coroutine_result = await coroutine_obj
        await asyncio.sleep(0.5)
        ll_task.cancel()
        self.lock = None
        return self.log_message, coroutine_result


class Snapshot:
    def __init__(self, snapshot_name, result_path: str = None):
        self.initial_snapshot = snapshot_name
        self.tmp_snapshot = self.initial_snapshot + "_TMP"
        if result_path is None:
            result_path = "../result"
        self.output_path = Path(result_path).joinpath(self.initial_snapshot)
        self.regular_supp_path = self.output_path.joinpath("REG")
        self.talkback_supp_path = self.output_path.joinpath("TB")
        if self.output_path.exists():
            shutil.rmtree(self.output_path.absolute())
        self.output_path.mkdir()
        self.regular_supp_path.mkdir()
        self.talkback_supp_path.mkdir()
        self.summary_path = self.output_path.joinpath("summary.txt")
        with open(self.summary_path, mode='w') as f:
            f.write(f"Result of Snapshot {self.initial_snapshot}\n")

    async def get_actions(self):
        if not await load_snapshot(self.initial_snapshot):
            print("Error in loading snapshot")
            return False
        dom = await capture_layout()
        dom_utf8 = dom.encode('utf-8')
        parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
        tree = etree.fromstring(dom_utf8, parser)
        commands = []
        for i, x in enumerate(tree.getiterator()):
            x_attrs = dict(x.attrib.items())
            if len(x.getchildren()) == 0:
                if x_attrs.get('displayed', 'true') == 'false':
                    continue
                info = {'class': x_attrs.get('class', ''),
                        'text': x_attrs.get('text', ''),
                        'contentDescription': x_attrs.get('content-desc', ''),
                        'resourceId': x_attrs.get('resource-id', ''),
                        'xpath': get_xpath(x),
                        'located_by': 'xpath',
                        'skip': False,
                        'action': 'click'}
                command = str(json.dumps(info))
                commands.append(command)
        return commands

    def is_navigation_done(self) -> bool:
        return asyncio.run(local_android_file_exists(FINAL_NAV_FILE))

    async def _setup_a11y_services(self, tb=False) -> None:
        if tb:
            await A11yServiceManager.enable("tb")
        else:
            await A11yServiceManager.disable("tb")
        if not await A11yServiceManager.is_enabled("latte"):
            await A11yServiceManager.enable("latte")
            await asyncio.sleep(1)

    def emulator_setup(self) -> bool:
        async def inner_setup():
            if not await load_snapshot(self.initial_snapshot):
                print("Error in loading snapshot")
                return False
            await self._setup_a11y_services(tb=True)
            await send_command_to_latte("nav_clear_history")
            print("Enabled A11y Services:", await A11yServiceManager.get_enabled_services())
            await save_snapshot(self.tmp_snapshot)
            return True
        return asyncio.run(inner_setup())

    async def setup_talkback_executor(self):
        await self._setup_a11y_services(tb=True)
        await send_command_to_latte("set_step_executor", "talkback")
        await send_command_to_latte("set_delay", "2000")
        await send_command_to_latte("set_physical_touch", "false")
        await send_command_to_latte("enable")

    async def setup_regular_executor(self):
        await self._setup_a11y_services(tb=False)
        await send_command_to_latte("set_step_executor", "regular")
        await send_command_to_latte("set_delay", "2000")
        await send_command_to_latte("set_physical_touch", "true")
        await send_command_to_latte("enable")

    async def tb_navigate_next(self, index: int) -> str:
        if not await load_snapshot(self.tmp_snapshot):
            print("Error in loading snapshot")
            return None
        print("Perform Next!")
        await self._setup_a11y_services(tb=True)
        await send_command_to_latte("nav_next")
        next_command_json = await cat_local_android_file(FINAL_ACITON_FILE)
        print("Next Command is " + next_command_json)
        async with aiofiles.open(self.summary_path, mode='a') as f:
            await f.write(f"{index}: [{next_command_json}]\n")
        print("Get another snapshot")
        await save_snapshot(self.tmp_snapshot)
        return next_command_json

    async def tb_perform_select(self, index) -> None:
        print("Perform Select!")
        await send_command_to_latte("nav_select")
        await cat_local_android_file(FINAL_ACITON_FILE)
        layout = await capture_layout()
        async with aiofiles.open(self.talkback_supp_path.joinpath(f"{index}.xml"), mode='w') as f:
            await f.write(layout)

    async def reg_perform_select(self, select_command, index) -> None:
        print("Now with regular executor")
        await self.setup_regular_executor()
        await send_command_to_latte("do_step", select_command)
        await asyncio.sleep(2)  # TODO: need to change
        layout = await capture_layout()
        async with aiofiles.open(self.regular_supp_path.joinpath(f"{index}.xml"), mode='w') as f:
            await f.write(layout)

    def explore(self):
        if not self.emulator_setup():
            print("Error in emulator setup!")
            return
        count = 0
        client = AdbClient(host="127.0.0.1", port=5037)
        device = asyncio.run(client.device("emulator-5554"))
        padb_logger = ParallelADBLogger(device)
        tb_commands = []
        while not self.is_navigation_done():
            count += 1
            print("Count:", count)
            next_command_json = asyncio.run(self.tb_navigate_next(count))
            if next_command_json is None:
                return
            if self.is_navigation_done():
                break
            tb_commands.append(next_command_json)
            log_message, tb_result = asyncio.run(padb_logger.execute_async_with_log(self.tb_perform_select(count)))
            with open(self.talkback_supp_path.joinpath(f"{count}.log"), mode='w') as f:
                f.write(log_message)
            if not asyncio.run(load_snapshot(self.tmp_snapshot)):
                print("Error in loading snapshot")
                return False
            log_message, reg_result = asyncio.run(padb_logger.execute_async_with_log(self.reg_perform_select(next_command_json, count)))
            with open(self.regular_supp_path.joinpath(f"{count}.log"), mode='w') as f:
                f.write(log_message)
            print("Groundhug Day!")
        print("Done")
        return tb_commands

def bm_explore():
    snapshot = Snapshot("todo_0")
    possible_commands = asyncio.run(snapshot.get_actions())
    tb_commands = snapshot.explore()
    # snapshot.explore()

# async def explore(initial_snapshot: str) -> None:
#     LAST_SNAPSHOT = "BM_SNAPSHOT"
#     # BASE_DIR = pathlib.Path(__file__).parent.absolute().parent
#     # RESULT_PATH = BASE_DIR.joinpath("result")
#     OUTPUT_PATH = RESULT_PATH.joinpath(initial_snapshot)
#     REG_OUTPUT_PATH =OUTPUT_PATH.joinpath("REG")
#     TB_OUTPUT_PATH = OUTPUT_PATH.joinpath("TB")
#     if OUTPUT_PATH.exists():
#         shutil.rmtree(OUTPUT_PATH.absolute())
#     OUTPUT_PATH.mkdir()
#     REG_OUTPUT_PATH.mkdir()
#     TB_OUTPUT_PATH.mkdir()
#     RESULT_FILE = OUTPUT_PATH.joinpath("summary.txt")
#     # Initial Setup
#     if not await initial_setup(initial_snapshot, LAST_SNAPSHOT, RESULT_FILE):
#         return
#     # End of Initial Setup
#     COUNT = 0
#     while not await local_android_file_exists(FINAL_NAV_FILE):
#         COUNT += 1
#         print("Count:", COUNT)
#         # Navigate Next
#         NEXT_COMMAND = await tb_navigate_next(LAST_SNAPSHOT, FINAL_ACITON_FILE, RESULT_FILE, COUNT)
#         if NEXT_COMMAND is None:
#             return
#         if await local_android_file_exists(FINAL_NAV_FILE):
#             break
#         # End of Navigate Next
#         await tb_perform_select(FINAL_ACITON_FILE, TB_OUTPUT_PATH, COUNT)
#         if not await reg_perform_select(NEXT_COMMAND, REG_OUTPUT_PATH, COUNT, LAST_SNAPSHOT):
#             return
#         print("Groundhug Day!")
#
#     print(await cat_local_android_file(FINAL_ACITON_FILE))
#
# log_list = ""
#
#
# async def logcat(connection):
#     global log_list
#     while True:
#         data = await connection.read(1024)
#         if not data:
#             break
#         log_list += data.decode('utf-8')+'\n'
#     await connection.close()
#
#
# async def _logcat(device):
#     conn = await device.create_connection(timeout=None)
#     cmd = "shell:{}".format("logcat -c; logcat")
#     await conn.send(cmd)
#     await logcat(conn)
#
#
# async def alaki_loop():
#     c = 0
#     while True:
#         print("  ", c)
#         c += 1
#         await asyncio.sleep(1)


async def main():
    client = AdbClient(host="127.0.0.1", port=5037)
    device = await client.device("emulator-5554")
    # client = AdbClient(host="127.0.0.1", port=5037)
    # devices = await client.devices()
    # for device in devices:
    #     print(device.serial)
    from datetime import datetime

    now = datetime.now()

    # print("Current Time =", datetime.now().strftime("%H:%M:%S"))
    # print("S: ", await device.shell("date"))
    # screenshot_task = asyncio.create_task(save_screenshot(device, "alaki.png"))
    # ll_task = asyncio.create_task(_logcat(device))
    # await screenshot_task
    # await asyncio.sleep(0.5)
    # ll_task.cancel()
    # print("End =", datetime.now().strftime("%H:%M:%S"))
    # print("E: ", await device.shell("date"))
    # print('\n\n\n')
    # print("\n".join(log_list.split('\n')[:5]))
    # print("\n".join(log_list.split('\n')[-5:]))
    # result = await asyncio.gather(*[save_screenshot(device, "alaki.png") for device in devices])
    # print(result)


if __name__ == "__main__":
    bm_explore()
    # cmd = "ls"
    # return_code, stdout, stderr = asyncio.run(run_bash(cmd))
    # print(f'[{cmd!r} exited with {return_code}]')
    # if stdout:
    #     print(f'[stdout]\n{stdout.decode()}')
    # if stderr:
    #     print(f'[stderr]\n{stderr.decode()}')
    # asyncio.run(load_snapshot("todo_0"))
    # asm = A11yServiceManager()

    # print("Enabled Services:", asyncio.run(asm.get_enabled_services()))
    # asyncio.run(asm.enable("tb"))
    # print("Enabled Services:", asyncio.run(asm.get_enabled_services()))
    # asyncio.run(asm.enable("latte"))
    # print("Enabled Services:", asyncio.run(asm.get_enabled_services()))
    # asyncio.run(asm.disable("latte"))
    # print("Enabled Services:", asyncio.run(asm.get_enabled_services()))
    # asyncio.run(asm.disable("latte"))
    # print("Enabled Services:", asyncio.run(asm.get_enabled_services()))
    # asyncio.run(asm.disable("tb"))
    # print("Enabled Services:", asyncio.run(asm.get_enabled_services()))
    # print(asyncio.run(local_android_file_exists("alaki")))
    # print(asyncio.run(cat_local_android_file("dolaki", verbose=True)))
    # asyncio.run(send_command_to_latte("set_step_executor", "regular"))
    # asyncio.run(explore("todo_0"))

