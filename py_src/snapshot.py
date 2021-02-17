import asyncio
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import List
from ppadb.client_async import ClientAsync as AdbClient

from GUI_utils import get_elements
from a11y_service import A11yServiceManager
from adb_utils import capture_layout, load_snapshot, save_snapshot
from latte_utils import is_navigation_done, \
    talkback_nav_command, tb_navigate_next, tb_perform_select,\
    reg_perform_select
from padb_utils import ParallelADBLogger, save_screenshot


class Snapshot:
    def __init__(self, snapshot_name, result_path: str = None):
        self.initial_snapshot = snapshot_name
        self.tmp_snapshot = self.initial_snapshot + "_TMP"
        if result_path is None:
            result_path = "../result"
        self.output_path = Path(result_path).joinpath(self.initial_snapshot)
        self.regular_supp_path = self.output_path.joinpath("REG")
        self.talkback_supp_path = self.output_path.joinpath("TB")
        self.summary_path = self.output_path.joinpath("summary.txt")
        client = AdbClient(host="127.0.0.1", port=5037)
        self.device = asyncio.run(client.device("emulator-5554"))

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

    def explore(self):
        if not self.emulator_setup():
            print("Error in emulator setup!")
            return
        if self.output_path.exists():
            shutil.rmtree(self.output_path.absolute())
        self.output_path.mkdir()
        self.regular_supp_path.mkdir()
        self.talkback_supp_path.mkdir()
        with open(self.summary_path, mode='w') as f:
            f.write("")
        count = 0
        padb_logger = ParallelADBLogger(self.device)
        visible_elements = get_elements()
        valid_resource_ids = set()
        valid_xpaths = set()
        for element in visible_elements:
            if element['resourceId']:
                valid_resource_ids.add(element['resourceId'])
            if element['xpath']:
                valid_xpaths.add(element['xpath'])
        visited_resource_ids = set()
        visited_xpath_count = defaultdict(int)
        tb_commands = []
        reload_snapshot = True
        while not is_navigation_done():
            count += 1
            print("Count:", count)
            if reload_snapshot:
                if not asyncio.run(load_snapshot(self.tmp_snapshot)):
                    print("Error in loading snapshot")
                    return None
            next_command_str = asyncio.run(tb_navigate_next())
            reload_snapshot = True
            if next_command_str is None:
                return
            if is_navigation_done():
                break
            next_command_json = json.loads(next_command_str)
            if next_command_json['xpath'] != 'null':
                visited_xpath_count[next_command_json['xpath']] += 1
                if visited_xpath_count[next_command_json['xpath']] > 3:
                    break
            if next_command_str in tb_commands \
                    or next_command_json['resourceId'] in visited_resource_ids\
                    or next_command_json['xpath'] not in valid_xpaths\
                    or visited_xpath_count[next_command_json['xpath']] > 1:
                print("Repetitive or unimportant element!")
                count -= 1
                reload_snapshot = False
                continue
            if next_command_json['resourceId'] != 'null':
                visited_resource_ids.add(next_command_json['resourceId'])
            print("Next Command is " + next_command_str)
            with open(self.summary_path, mode='a') as f:
                f.write(f"{count}: {next_command_str}\n")
            print("Get another snapshot")
            asyncio.run(save_screenshot(self.device, str(self.talkback_supp_path.joinpath(f"{count}.png"))))
            asyncio.run(save_snapshot(self.tmp_snapshot))
            tb_commands.append(next_command_str)
            log_message, tb_layout = asyncio.run(padb_logger.execute_async_with_log(tb_perform_select()))
            with open(self.talkback_supp_path.joinpath(f"{count}.xml"), mode='w') as f:
                f.write(tb_layout)
            with open(self.talkback_supp_path.joinpath(f"{count}.log"), mode='w') as f:
                f.write(log_message)
            if not asyncio.run(load_snapshot(self.tmp_snapshot)):
                print("Error in loading snapshot")
                return False
            log_message, reg_layout = asyncio.run(
                padb_logger.execute_async_with_log(reg_perform_select(next_command_str)))
            with open(self.regular_supp_path.joinpath(f"{count}.xml"), mode='w') as f:
                f.write(reg_layout)
            with open(self.regular_supp_path.joinpath(f"{count}.log"), mode='w') as f:
                f.write(log_message)
            print("Groundhug Day!")
        print("Done")
        return tb_commands

    def get_important_actions(self) -> List:
        if not asyncio.run(load_snapshot(self.initial_snapshot)):
            print("Error in loading snapshot")
            return []
        important_elements = get_elements(
            query=lambda x: x.attrib.get('clickable', 'false') == 'true' or x.attrib.get('NAF', 'false') == 'true')
        visited_resource_ids = set()
        refined_list = []
        for e in important_elements:
            if e['resourceId']:
                if e['resourceId'] in visited_resource_ids:
                    continue
                visited_resource_ids.add(e['resourceId'])
            refined_list.append(e)
        return refined_list

    def get_tb_done_actions(self):
        tb_visited = []
        with open(self.summary_path) as f:
            aa = f.read()
            for x in aa.split('\n'):
                x = x[x.find(':') + 1:].strip()
                if x:
                    tb_visited.append(json.loads(x))
        return tb_visited

    def get_meaningful_actions(self, action_list: List) -> List:
        if not asyncio.run(load_snapshot(self.initial_snapshot)):
            print("Error in loading snapshot")
            return []
        original_layout = asyncio.run(capture_layout())
        meaningful_actions = []
        for action in action_list:
            if not asyncio.run(load_snapshot(self.initial_snapshot)):
                print("Error in loading snapshot")
                return []
            reg_layout = asyncio.run(reg_perform_select(json.dumps(action)))
            if reg_layout != original_layout:
                meaningful_actions.append(action)
        return meaningful_actions
