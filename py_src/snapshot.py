import logging
import asyncio
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Callable, List, Optional, Union
from ppadb.client_async import ClientAsync as AdbClient

from GUI_utils import get_elements
from a11y_service import A11yServiceManager
from adb_utils import load_snapshot, save_snapshot, get_current_activity_name, \
    is_android_activity_on_top
from latte_utils import latte_capture_layout as capture_layout
from latte_utils import talkback_nav_command, tb_navigate_next, tb_perform_select, \
    reg_execute_command, stb_execute_command, get_missing_actions, ExecutionResult
from padb_utils import ParallelADBLogger, save_screenshot
from utils import annotate_rectangle

logger = logging.getLogger(__name__)
VISIT_LIMIT = 3


class AddressBook:
    def __init__(self, snapshot_result_path: Union[Path, str]):
        if isinstance(snapshot_result_path, str):
            snapshot_result_path = Path(snapshot_result_path)
        self.snapshot_result_path = snapshot_result_path
        self.visited_elements = []
        self.actions = []
        navigate_modes = ["tb", "reg", "exp", "s_reg", "s_tb", "s_exp"]
        self.mode_path_map = {}
        for mode in navigate_modes:
            self.mode_path_map[mode] = self.snapshot_result_path.joinpath(mode.upper())
        self.action_path = self.snapshot_result_path.joinpath("action.jsonl")
        self.visited_elements_path = self.snapshot_result_path.joinpath("visited.jsonl")
        self.s_action_path = self.snapshot_result_path.joinpath("s_action.jsonl")

    def initiate(self):
        if self.snapshot_result_path.exists():
            shutil.rmtree(self.snapshot_result_path.absolute())
        self.snapshot_result_path.mkdir()
        for path in self.mode_path_map.values():
            path.mkdir()
        self.action_path.touch()
        self.visited_elements_path.touch()
        self.s_action_path.touch()

    def get_screenshot_path(self, mode: str, index: Union[int, str], extension: str = None, should_exists: bool = False):
        file_name = f"{index}_{extension}.png" if extension else f"{index}.png"
        return self._get_path(mode, file_name, should_exists)

    def get_layout_path(self, mode: str, index: int, should_exists: bool = False):
        return self._get_path(mode, f"{index}.xml", should_exists)

    def get_log_path(self, mode: str, index: int, is_layout: bool = False, should_exists: bool = False):
        file_name = f"{index}_layout.log" if is_layout else f"{index}.log"
        return self._get_path(mode, file_name, should_exists)

    def get_activity_name_path(self, mode: str, index: int, should_exists: bool = False):
        return self._get_path(mode, f"{index}_activity_name.txt", should_exists)

    def _get_path(self, mode: str, file_name_with_extension: str, should_exists: bool):
        if mode not in self.mode_path_map:
            return None
        path = self.mode_path_map[mode].joinpath(file_name_with_extension)
        if should_exists and not path.exists():
            return None
        return path


class ResultWriter:
    def __init__(self, address_book: AddressBook):
        self.address_book = address_book
        self.visited_elements = []
        self.actions = []

    def visit_element(self, element: dict):
        visited_element = {'index': len(self.visited_elements), 'element': element}
        self.visited_elements.append(visited_element)
        with open(self.address_book.visited_elements_path, "a") as f:
            f.write(f"{json.dumps(visited_element)}\n")

    def get_action_index(self):
        return len(self.actions)

    def add_action(self,
                   element: dict,
                   tb_action_result: str,
                   reg_action_result: ExecutionResult):
        action_index = self.get_action_index()
        exp_screenshot_path = self.address_book.get_screenshot_path('exp', action_index, should_exists=True)
        if exp_screenshot_path:
            annotate_rectangle(exp_screenshot_path,
                               self.address_book.get_screenshot_path('exp', action_index, extension="edited"),
                               reg_action_result.bound,
                               outline=(0, 255, 255),
                               scale=15,
                               width=15,)
        new_action = {'index': action_index,
                      'element': element,
                      'tb_action_result': tb_action_result,
                      'reg_action_result': reg_action_result,
                      }
        self.actions.append(new_action)
        with open(self.address_book.action_path, "a") as f:
            f.write(f"{json.dumps(new_action)}\n")

    def start_explore(self):
        self.address_book.initiate()

    async def capture_current_state(self, device, mode: str, index: int, has_layout=True,  log_message: Optional[str] = None) -> str:
        await save_screenshot(device, self.address_book.get_screenshot_path(mode, index))
        activity_name = await get_current_activity_name()
        with open(self.address_book.get_activity_name_path(mode, index), mode='w') as f:
            f.write(activity_name + "\n")

        layout = ""
        if has_layout:
            padb_logger = ParallelADBLogger(device)
            log, layout = await padb_logger.execute_async_with_log(capture_layout())
            with open(self.address_book.get_log_path(mode, index, is_layout=True), mode='w') as f:
                f.write(log)
            with open(self.address_book.get_layout_path(mode, index), mode='w') as f:
                f.write(layout)

        if log_message:
            with open(self.address_book.get_log_path(mode, index), mode='w') as f:
                f.write(log_message)

        return layout  # TODO: Remove it


class Snapshot:
    def __init__(self, snapshot_name, address_book: AddressBook):
        self.initial_snapshot = snapshot_name
        self.tmp_snapshot = self.initial_snapshot + "_TMP"
        self.address_book = address_book
        self.writer = ResultWriter(address_book)
        # -------------
        self.visible_elements = []
        self.valid_resource_ids = set()
        self.valid_xpaths = set()
        self.visited_resource_ids = set()
        self.visited_xpath_count = defaultdict(int)
        self.tb_commands = []
        # -------------
        self.device = None  # TODO: Not good

    async def emulator_setup(self) -> bool:
        if not await load_snapshot(self.initial_snapshot):
            logger.error("Error in loading snapshot")
            return False
        if await is_android_activity_on_top():
            logger.error("The snapshot is broken!")
            return False
        client = AdbClient(host="127.0.0.1", port=5037)  # TODO: Should be configured
        self.device = await client.device("emulator-5554")  # TODO: Not good
        await A11yServiceManager.setup_latte_a11y_services(tb=True)
        await talkback_nav_command("clear_history")
        logger.info("Enabled A11y Services:" + str(await A11yServiceManager.get_enabled_services()))
        await asyncio.sleep(3)
        await save_snapshot(self.tmp_snapshot)
        # ------------- TODO: think about it later ----------
        dom = await capture_layout()
        self.visible_elements = get_elements(dom)
        self.valid_resource_ids = set()
        self.valid_xpaths = set()
        for element in self.visible_elements:
            if element['resourceId']:
                self.valid_resource_ids.add(element['resourceId'])
            if element['xpath']:
                self.valid_xpaths.add(element['xpath'])
        self.visited_resource_ids = set()
        self.visited_xpath_count = defaultdict(int)
        self.tb_commands = []
        # -------------
        return True

    async def navigate_next(self) -> Optional[str]:
        if not await load_snapshot(self.tmp_snapshot):
            logger.debug("Error in loading snapshot")
            return None
        while True:
            next_command_str = await tb_navigate_next()
            if next_command_str is None:
                logger.error("TalkBack cannot navigate to the next element")
                return None
            next_command_json = json.loads(next_command_str)
            self.writer.visit_element(next_command_json)
            if next_command_json['xpath'] != 'null':
                self.visited_xpath_count[next_command_json['xpath']] += 1
                if self.visited_xpath_count[next_command_json['xpath']] > VISIT_LIMIT:
                    logger.info(
                        f"The XPath {next_command_json['xpath']} is visited more than {VISIT_LIMIT} times, break. ")
                    return None
            # TODO: Write the result of next_command_json somewhere
            # TODO: Update visited* with next_command_json
            # TODO: Skip if the position is also the same
            if next_command_str in self.tb_commands:
                logger.info("Has seen this command before!")
                continue
            if next_command_json['resourceId'] in self.visited_resource_ids:
                logger.info("Has seen this resourceId")
                continue
            if next_command_json['xpath'] not in self.valid_xpaths:
                logger.info("Not a valid xpath!")
                continue
            if self.visited_xpath_count[next_command_json['xpath']] > 1:  # TODO: Configurable
                logger.info("Has seen this xpath more than twice")
                continue
            # TODO: make it a counter
            if next_command_json['resourceId'] != 'null':
                self.visited_resource_ids.add(next_command_json['resourceId'])
            break
        return next_command_str

    async def explore(self) -> bool:
        if not await self.emulator_setup():
            logger.error("Error in emulator setup!")
            return False
        initial_layout = await capture_layout()
        self.writer.start_explore()
        padb_logger = ParallelADBLogger(self.device)
        is_in_app_activity = not await is_android_activity_on_top()
        while True and is_in_app_activity:
            logger.info(f"Action Index: {self.writer.get_action_index()}")
            # ------------------- Navigate Next -------------------
            click_command_str = await self.navigate_next()
            if not click_command_str:
                logger.info("Navigation is finished!")
                break
            logger.debug("Click Command is " + click_command_str)
            await self.writer.capture_current_state(self.device, "exp", self.writer.get_action_index(), has_layout=False)
            # if 'bound' in json.loads(click_command_str):
            #     bound = tuple(int(x) for x in (json.loads(click_command_str)['bound'].strip()).split('-'))
            # else:
            #     logger.error(f"The focused element doesn't have a bound! Element: {click_command_str}")
            logger.info("Get another snapshot")
            await save_snapshot(self.tmp_snapshot)
            self.tb_commands.append(click_command_str)
            # ------------------- End Navigate Next -------------------
            # ------------------- Start TalkBack Select ---------------
            log_message, tb_result = await padb_logger.execute_async_with_log(tb_perform_select())
            tb_layout = await self.writer.capture_current_state(self.device, "tb", self.writer.get_action_index(), log_message=log_message)
            # ------------------- End TalkBack Select ---------------
            # ------------------- Start Regular Select ---------------
            if not await load_snapshot(self.tmp_snapshot):
                logger.error("Error in loading snapshot")
                return False
            logger.info("Now with regular executor")
            log_message, reg_result = await padb_logger.execute_async_with_log(reg_execute_command(click_command_str))
            reg_layout = await self.writer.capture_current_state(self.device, "reg", self.writer.get_action_index(), log_message=log_message)
            # ------------------- End Regular Select ---------------
            self.writer.add_action(element=json.loads(click_command_str),
                                   tb_action_result=tb_result,
                                   reg_action_result=reg_result)
            logger.info("Groundhug Day!")
        logger.info("Done Exploring!")
        return True

    def get_important_actions(self) -> List:
        if not asyncio.run(load_snapshot(self.initial_snapshot)):
            logger.error("Error in loading snapshot")
            return []
        dom = asyncio.run(capture_layout())
        important_elements = get_elements(dom,
                                          filter_query=lambda x: x.attrib.get('clickable', 'false') == 'true'
                                                                 or x.attrib.get('NAF', 'false') == 'true')
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
        explore_result = []
        with open(self.address_book.action_path) as f:
            for line in f.readlines():
                explore_result.append(json.loads(line))
        for action in explore_result:
            result.append(action['element'])
        return result

    def get_meaningful_actions(self, action_list: List, executor: Callable = reg_execute_command) -> List:
        if not asyncio.run(load_snapshot(self.initial_snapshot)):
            logger.error("Error in loading snapshot")
            return []
        original_layout = asyncio.run(capture_layout())
        meaningful_actions = []
        for action in action_list:
            if not asyncio.run(load_snapshot(self.initial_snapshot)):
                logger.error("Error in loading snapshot")
                return []
            reg_layout, result = asyncio.run(executor(json.dumps(action)))
            if reg_layout != original_layout:
                meaningful_actions.append(action)
        return meaningful_actions

    def validate_by_stb(self):
        logger.info("Validating remaining actions.")
        important_actions = self.get_important_actions()
        tb_done_actions = self.get_tb_done_actions()
        tb_undone_actions = get_missing_actions(important_actions, tb_done_actions)
        logger.info(f"There are {len(tb_undone_actions)} missing actions in explore!")
        if not asyncio.run(load_snapshot(self.initial_snapshot)):
            logger.error("Error in loading snapshot")
            return []
        asyncio.run(asyncio.sleep(2))
        initial_layout = asyncio.run(capture_layout())
        asyncio.run(save_screenshot(self.device, self.address_book.get_screenshot_path('s_exp', 'INITIAL')))
        stb_result_list = {}
        all_activity_names = []
        is_in_app_activity = not asyncio.run(is_android_activity_on_top())
        if is_in_app_activity:
            for index, action in enumerate(tb_undone_actions):
                logger.info(f"Missing action {index}")
                if not asyncio.run(load_snapshot(self.initial_snapshot)):
                    logger.error("Error in loading snapshot")
                    return []
                reg_result = asyncio.run(reg_execute_command(json.dumps(action)))
                reg_layout = asyncio.run(self.writer.capture_current_state(self.device, "s_reg", index))
                if reg_layout == initial_layout or reg_result.state != 'COMPLETED':  # the action is not meaningful
                    continue
                all_activity_names.append(f"REG_C $ {index} $ {asyncio.run(get_current_activity_name())}")
                annotate_rectangle(self.address_book.get_screenshot_path('s_exp', 'INITIAL'),
                                   self.address_book.get_screenshot_path('s_exp', 'INITIAL', extension="R"),
                                   reg_result.bound,
                                   outline=(255, 0, 255),
                                   width=5,
                                   scale=1)
                if not asyncio.run(load_snapshot(self.initial_snapshot)):
                    logger.error("Error in loading snapshot")
                    return []
                stb_result = asyncio.run(stb_execute_command(json.dumps(action)))
                stb_layout = asyncio.run(self.writer.capture_current_state(self.device, "s_tb", index))
                all_activity_names.append(f"STB_C $ {index} $ {asyncio.run(get_current_activity_name())}")
                annotate_rectangle(self.address_book.get_screenshot_path('s_exp', 'INITIAL', extension="R"),
                                   self.address_book.get_screenshot_path('s_exp', 'INITIAL', extension="RS"),
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
        with open(self.address_book.s_action_path, "w") as f:
            json.dump(stb_result_list, f)
        with open(str(self.address_book.mode_path_map['s_tb'].absolute()) + "_activities.txt", "w") as f:
            f.writelines(all_activity_names)

    def old_report_issues(self):
        different_behaviors = []
        directional_unreachable = []
        unlocatable = []
        different_behaviors_directional_unreachable = []
        tb_xpaths = {}
        pending = False
        if self.address_book.snapshot_result_path.joinpath("explore.json").exists():
            with open(self.address_book.snapshot_result_path.joinpath("explore.json")) as f:
                explore_result = json.load(f)
                for index in explore_result:
                    tb_xpaths[explore_result[index]['command']['xpath']] = explore_result[index]['command']
                    if not explore_result[index]['same']:
                        different_behaviors.append(explore_result[index]['command'])
        else:
            pending = True

        if self.address_book.snapshot_result_path.joinpath("stb_result.json").exists():
            with open(self.address_book.snapshot_result_path.joinpath("stb_result.json")) as f:
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
        return different_behaviors, directional_unreachable, unlocatable, \
               different_behaviors_directional_unreachable, pending
