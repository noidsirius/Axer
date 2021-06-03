import asyncio
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Callable, List, Optional
from ppadb.client_async import ClientAsync as AdbClient

from GUI_utils import get_elements
from a11y_service import A11yServiceManager
from adb_utils import capture_layout, load_snapshot, save_snapshot
from latte_utils import is_navigation_done, \
    talkback_nav_command, tb_navigate_next, tb_perform_select, \
    reg_execute_command, stb_execute_command, get_missing_actions, ExecutionResult
from padb_utils import ParallelADBLogger, save_screenshot
from utils import annotate_rectangle


class Snapshot:
    def __init__(self, snapshot_name, result_path: str = None):
        self.initial_snapshot = snapshot_name
        self.tmp_snapshot = self.initial_snapshot + "_TMP"
        if result_path is None:
            result_path = "../result"
        self.output_path = Path(result_path).joinpath(self.initial_snapshot)
        self.regular_supp_path = self.output_path.joinpath("REG")
        self.talkback_supp_path = self.output_path.joinpath("TB")
        self.explore_supp_path = self.output_path.joinpath("EXP")
        self.explore_result_path = self.output_path.joinpath("explore.json")
        self.stb_result_path = self.output_path.joinpath("stb_result.json")
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
            await asyncio.sleep(3)
            await save_snapshot(self.tmp_snapshot)
            return True

        return asyncio.run(inner_setup())

    def explore(self):
        if not self.emulator_setup():
            print("Error in emulator setup!")
            return
        initial_layout = asyncio.run(capture_layout())
        if self.output_path.exists():
            shutil.rmtree(self.output_path.absolute())
        self.output_path.mkdir()
        self.regular_supp_path.mkdir()
        self.talkback_supp_path.mkdir()
        self.explore_supp_path.mkdir()
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
        explore_result = {}
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
                    or next_command_json['resourceId'] in visited_resource_ids \
                    or next_command_json['xpath'] not in valid_xpaths \
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
            asyncio.run(save_screenshot(self.device, str(self.explore_supp_path.joinpath(f"{count}.png"))))
            asyncio.run(save_snapshot(self.tmp_snapshot))
            tb_commands.append(next_command_str)
            log_message, (tb_layout, tb_result) = asyncio.run(padb_logger.execute_async_with_log(tb_perform_select()))
            self.capture_current_state(str(count), tb_layout, self.talkback_supp_path, log_message=log_message)
            if not asyncio.run(load_snapshot(self.tmp_snapshot)):
                print("Error in loading snapshot")
                return False
            print("Now with regular executor")
            log_message, (reg_layout, reg_result) = asyncio.run(
                padb_logger.execute_async_with_log(reg_execute_command(next_command_str)))
            self.capture_current_state(str(count), reg_layout, self.regular_supp_path, log_message=log_message)
            annotate_rectangle(self.explore_supp_path.joinpath(f"{count}.png"),
                               self.explore_supp_path.joinpath(f"{count}_edited.png"),
                               reg_result.bound,
                               outline=(0, 255, 255),
                               scale=15,
                               width=15, )

            explore_result[count] = {'command': next_command_json,
                                     'same': tb_layout == reg_layout,
                                     'tb_result': tb_result,
                                     'reg_result': reg_result,
                                     'tb_no_change': tb_layout == initial_layout,
                                     'reg_no_change': reg_layout == initial_layout,
                                     }
            print("Groundhug Day!")
        print("Done")
        with open(self.explore_result_path, "w") as f:
            json.dump(explore_result, f)
        return tb_commands

    def capture_current_state(self, file_name: str, layout: str, path: Path, log_message: Optional[str] = None):
        with open(path.joinpath(f"{file_name}.xml"), mode='w') as f:
            f.write(layout)
        if log_message:
            with open(path.joinpath(f"{file_name}.log"), mode='w') as f:
                f.write(log_message)
        asyncio.run(save_screenshot(self.device, str(path.joinpath(f"{file_name}.png"))))

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
        result = []
        with open(self.explore_result_path) as f:
            explore_result = json.load(f)
        for index in explore_result:
            result.append(explore_result[index]['command'])
        return result

    def get_meaningful_actions(self, action_list: List, executor: Callable = reg_execute_command) -> List:
        if not asyncio.run(load_snapshot(self.initial_snapshot)):
            print("Error in loading snapshot")
            return []
        original_layout = asyncio.run(capture_layout())
        meaningful_actions = []
        for action in action_list:
            if not asyncio.run(load_snapshot(self.initial_snapshot)):
                print("Error in loading snapshot")
                return []
            reg_layout, result = asyncio.run(executor(json.dumps(action)))
            if reg_layout != original_layout:
                meaningful_actions.append(action)
        return meaningful_actions

    def validate_by_stb(self):
        important_actions = self.get_important_actions()
        tb_done_actions = self.get_tb_done_actions()
        tb_undone_actions = get_missing_actions(important_actions, tb_done_actions)
        if not asyncio.run(load_snapshot(self.initial_snapshot)):
            print("Error in loading snapshot")
            return []
        initial_layout = asyncio.run(capture_layout())
        asyncio.run(save_screenshot(self.device, str(self.explore_supp_path.joinpath(f"INITIAL.png"))))
        stb_result_list = {}
        for index, action in enumerate(tb_undone_actions):
            if not asyncio.run(load_snapshot(self.initial_snapshot)):
                print("Error in loading snapshot")
                return []
            reg_layout, reg_result = asyncio.run(reg_execute_command(json.dumps(action)))
            if reg_layout == initial_layout or reg_result.state != 'COMPLETED':  # the action is not meaningful
                continue
            self.capture_current_state(f"M_{index}", reg_layout, self.regular_supp_path)
            annotate_rectangle(self.explore_supp_path.joinpath(f"INITIAL.png"),
                               self.explore_supp_path.joinpath(f"I_{index}_R.png"),
                               reg_result.bound,
                               outline=(255, 0, 255),
                               width=5,
                               scale=1)
            if not asyncio.run(load_snapshot(self.initial_snapshot)):
                print("Error in loading snapshot")
                return []
            stb_layout, stb_result = asyncio.run(stb_execute_command(json.dumps(action)))
            self.capture_current_state(f"M_{index}", stb_layout, self.talkback_supp_path)
            annotate_rectangle(self.explore_supp_path.joinpath(f"I_{index}_R.png"),
                               self.explore_supp_path.joinpath(f"I_{index}_RS.png"),
                               stb_result.bound,
                               outline=(255, 255, 0),
                               width=15,
                               scale=20)
            a_result = {'index': index,
                        'command': action,
                        'same': reg_layout == stb_layout,
                        'stb_no_change': stb_layout == initial_layout,
                        'stb_result': stb_result,
                        'reg_result': reg_result,
                        }
            stb_result_list[action['xpath']] = a_result
        with open(self.stb_result_path, "w") as f:
            json.dump(stb_result_list, f)

    def report_issues(self):
        different_behaviors = []
        directional_unreachable = []
        unlocatable = []
        different_behaviors_directional_unreachable = []
        tb_xpaths = {}
        pending = False
        if self.explore_result_path.exists():
            with open(self.explore_result_path) as f:
                explore_result = json.load(f)
                for index in explore_result:
                    tb_xpaths[explore_result[index]['command']['xpath']] = explore_result[index]['command']
                    if not explore_result[index]['same']:
                        different_behaviors.append(explore_result[index]['command'])
        else:
            pending = True

        if self.stb_result_path.exists():
            with open(self.stb_result_path) as f:
                stb_results = json.load(f)
                for key in stb_results:
                    e = ExecutionResult(*stb_results[key]['stb_result'])
                    if e.state == 'COMPLETED_BY_HELP':
                        unlocatable.append(stb_results[key]['command'])
                    elif e.state == 'FAILED' or not stb_results[key]['same']:
                        different_behaviors_directional_unreachable.append(stb_results[key]['command'])
                    else:
                        if e.xpath not in tb_xpaths.keys():
                            directional_unreachable.append(stb_results[key]['command'])
        else:
            pending = True
        return different_behaviors, directional_unreachable, unlocatable, different_behaviors_directional_unreachable, pending
