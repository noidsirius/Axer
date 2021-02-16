import asyncio
import json
import shutil
from pathlib import Path

import aiofiles
from lxml import etree
from ppadb.client_async import ClientAsync as AdbClient

from a11y_service import A11yServiceManager
from adb_utils import cat_local_android_file, capture_layout, \
    local_android_file_exists, load_snapshot, save_snapshot
from padb_utils import ParallelADBLogger
from GUI_utils import get_xpath
from latte_utils import setup_regular_executor, talkback_nav_command, do_step, is_navigation_done

FINAL_ACITON_FILE = "finish_nav_action.txt"


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

    def emulator_setup(self) -> bool:
        async def inner_setup():
            if not await load_snapshot(self.initial_snapshot):
                print("Error in loading snapshot")
                return False
            await A11yServiceManager.setup_latte_a11y_services(tb=True)
            await talkback_nav_command("clear_history")
            print("Enabled A11y Services:", await A11yServiceManager.get_enabled_services())
            await save_snapshot(self.tmp_snapshot)
            return True

        return asyncio.run(inner_setup())

    async def tb_navigate_next(self, index: int) -> str:
        if not await load_snapshot(self.tmp_snapshot):
            print("Error in loading snapshot")
            return None
        print("Perform Next!")
        await A11yServiceManager.setup_latte_a11y_services(tb=True)
        await talkback_nav_command("next")
        next_command_json = await cat_local_android_file(FINAL_ACITON_FILE)
        print("Next Command is " + next_command_json)
        async with aiofiles.open(self.summary_path, mode='a') as f:
            await f.write(f"{index}: [{next_command_json}]\n")
        print("Get another snapshot")
        await save_snapshot(self.tmp_snapshot)
        return next_command_json

    async def tb_perform_select(self, index) -> None:
        print("Perform Select!")
        await talkback_nav_command("select")
        await cat_local_android_file(FINAL_ACITON_FILE)
        layout = await capture_layout()
        async with aiofiles.open(self.talkback_supp_path.joinpath(f"{index}.xml"), mode='w') as f:
            await f.write(layout)

    async def reg_perform_select(self, select_command, index) -> None:
        print("Now with regular executor")
        await setup_regular_executor()
        await do_step(select_command)
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
        while not is_navigation_done():
            count += 1
            print("Count:", count)
            next_command_json = asyncio.run(self.tb_navigate_next(count))
            if next_command_json is None:
                return
            if is_navigation_done():
                break
            tb_commands.append(next_command_json)
            log_message, tb_result = asyncio.run(padb_logger.execute_async_with_log(self.tb_perform_select(count)))
            with open(self.talkback_supp_path.joinpath(f"{count}.log"), mode='w') as f:
                f.write(log_message)
            if not asyncio.run(load_snapshot(self.tmp_snapshot)):
                print("Error in loading snapshot")
                return False
            log_message, reg_result = asyncio.run(
                padb_logger.execute_async_with_log(self.reg_perform_select(next_command_json, count)))
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


if __name__ == "__main__":
    bm_explore()
