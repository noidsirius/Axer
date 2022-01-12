import logging
import asyncio
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Callable, List, Optional
from ppadb.client_async import ClientAsync as AdbClient

from GUI_utils import get_elements
from a11y_service import A11yServiceManager
from adb_utils import capture_layout, load_snapshot, save_snapshot, get_current_activity_name, \
    is_android_activity_on_top
from latte_utils import talkback_nav_command, tb_navigate_next, tb_perform_select, \
    reg_execute_command, stb_execute_command, get_missing_actions, ExecutionResult
from padb_utils import ParallelADBLogger, save_screenshot
from utils import annotate_rectangle

logger = logging.getLogger(__name__)
VISIT_LIMIT = 3


class ResultWriter:
    def __init__(self, snapshot_name: str, result_path: str = None):
        if result_path is None:
            result_path = "../result"
        self.output_path = Path(result_path).joinpath(snapshot_name)  # TODO:
        self.regular_supp_path = self.output_path.joinpath("REG")
        self.talkback_supp_path = self.output_path.joinpath("TB")
        self.explore_supp_path = self.output_path.joinpath("EXP")
        self.explore_result_path = self.output_path.joinpath("explore.json")
        self.stb_result_path = self.output_path.joinpath("stb_result.json")
        self.summary_path = self.output_path.joinpath("summary.txt")

    def start_explore(self, snapshot_name: str):
        if self.output_path.exists():
            shutil.rmtree(self.output_path.absolute())
        self.output_path.mkdir()
        self.regular_supp_path.mkdir()
        self.talkback_supp_path.mkdir()
        self.explore_supp_path.mkdir()
        with open(self.summary_path, mode='w') as f:
            f.write("")

    def capture_current_state(self, device, file_name: str, layout: str, code: str, log_message: Optional[str] = None):
        r_path = ""
        if code == "tb":
            r_path = self.talkback_supp_path
        elif code == "reg":
            r_path = self.regular_supp_path
        elif code == "exp":
            r_path = self.explore_supp_path
        else:
            return
        with open(r_path.joinpath(f"{file_name}.xml"), mode='w') as f:
            f.write(layout)
        if log_message:
            with open(r_path.joinpath(f"{file_name}.log"), mode='w') as f:
                f.write(log_message)
        asyncio.run(save_screenshot(device, str(r_path.joinpath(f"{file_name}.png"))))


class Snapshot:
    def __init__(self, snapshot_name, result_path: str = None):
        self.initial_snapshot = snapshot_name
        self.tmp_snapshot = self.initial_snapshot + "_TMP"
        self.writer = ResultWriter(self.initial_snapshot, result_path)
        # -------------
        self.visible_elements = []
        self.valid_resource_ids = set()
        self.valid_xpaths = set()
        self.visited_resource_ids = set()
        self.visited_xpath_count = defaultdict(int)
        self.tb_commands = []
        # -------------
        self.device = None  # TODO: Not good

    def emulator_setup(self) -> bool:
        async def inner_setup():
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
            # -------------
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

        return asyncio.run(inner_setup())

    def navigate_next(self) -> Optional[str]:
        if not asyncio.run(load_snapshot(self.tmp_snapshot)):
            logger.debug("Error in loading snapshot")
            return None
        while True:
            next_command_str = asyncio.run(tb_navigate_next())
            if next_command_str is None:
                logger.error("TalkBack cannot navigate to the next element")
                return None
            next_command_json = json.loads(next_command_str)
            if next_command_json['xpath'] != 'null':
                self.visited_xpath_count[next_command_json['xpath']] += 1
                if self.visited_xpath_count[next_command_json['xpath']] > VISIT_LIMIT:
                    logger.info(
                        f"The XPath {next_command_json['xpath']} is visited more than {VISIT_LIMIT} times, break. ")
                    return None
            # TODO: Write the result of next_command_json somewhere
            # TODO: Update visited* with next_command_json
            # TODO: Skip if the position is also the same
            if next_command_str in self.tb_commands \
                    or next_command_json['resourceId'] in self.visited_resource_ids \
                    or next_command_json['xpath'] not in self.valid_xpaths \
                    or self.visited_xpath_count[next_command_json['xpath']] > 1:  # TODO: Configurable
                logger.info("Repetitive or unimportant element!")
                continue
            # TODO: make it a counter
            if next_command_json['resourceId'] != 'null':
                self.visited_resource_ids.add(next_command_json['resourceId'])
            break
        return next_command_str

    def explore(self) -> bool:
        if not self.emulator_setup():
            logger.error("Error in emulator setup!")
            return False
        initial_layout = asyncio.run(capture_layout())
        self.writer.start_explore(self.initial_snapshot)
        count = 0
        padb_logger = ParallelADBLogger(self.device)
        explore_result = {}
        all_activity_names = []
        is_in_app_activity = not asyncio.run(is_android_activity_on_top())
        while True and is_in_app_activity:
            count += 1
            logger.info(f"Count: {count}")
            all_activity_names.append(f"TB_N $ {count} $ {asyncio.run(get_current_activity_name())}")
            # ------------------- Navigate Next -------------------
            click_command_str = self.navigate_next()
            if not click_command_str:
                logger.info("Navigation is finished!")
                break
            logger.debug("Click Command is " + click_command_str)
            # with open(self.summary_path, mode='a') as f:
            #     f.write(f"{count}: {next_command_str}\n")
            logger.info("Get another snapshot")
            asyncio.run(save_screenshot(self.device, str(self.writer.explore_supp_path.joinpath(f"{count}.png"))))
            asyncio.run(save_snapshot(self.tmp_snapshot))
            self.tb_commands.append(click_command_str)
            # ------------------- End Navigate Next -------------------
            # ------------------- Start TalkBack Select ---------------
            log_message, (tb_layout, tb_result) = asyncio.run(padb_logger.execute_async_with_log(tb_perform_select()))
            self.writer.capture_current_state(self.device, str(count), tb_layout, "tb", log_message=log_message)
            all_activity_names.append(f"TB_C $ {count} $ {asyncio.run(get_current_activity_name())}")
            # ------------------- End TalkBack Select ---------------
            # ------------------- Start Regular Select ---------------
            if not asyncio.run(load_snapshot(self.tmp_snapshot)):
                logger.error("Error in loading snapshot")
                return False
            logger.info("Now with regular executor")
            log_message, (reg_layout, reg_result) = asyncio.run(
                padb_logger.execute_async_with_log(reg_execute_command(click_command_str)))
            self.writer.capture_current_state(self.device, str(count), reg_layout, "reg", log_message=log_message)
            all_activity_names.append(f"RG_C $ {count} $ {asyncio.run(get_current_activity_name())}")
            # ------------------- End Regular Select ---------------
            annotate_rectangle(self.writer.explore_supp_path.joinpath(f"{count}.png"),
                               self.writer.explore_supp_path.joinpath(f"{count}_edited.png"),
                               reg_result.bound,
                               outline=(0, 255, 255),
                               scale=15,
                               width=15, )

            explore_result[count] = {'command': json.loads(click_command_str),
                                     'same': tb_layout == reg_layout,
                                     'tb_result': tb_result,
                                     'reg_result': reg_result,
                                     'tb_no_change': tb_layout == initial_layout,
                                     'reg_no_change': reg_layout == initial_layout,
                                     }
            logger.info("Groundhug Day!")
        logger.info("Done")
        with open(self.writer.explore_result_path, "w") as f:
            json.dump(explore_result, f)
        with open(str(self.writer.explore_result_path.absolute()) + "_activities.txt", "w") as f:
            f.writelines(all_activity_names)
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
        with open(self.writer.explore_result_path) as f:
            explore_result = json.load(f)
        for index in explore_result:
            result.append(explore_result[index]['command'])
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
        important_actions = self.get_important_actions()
        tb_done_actions = self.get_tb_done_actions()
        tb_undone_actions = get_missing_actions(important_actions, tb_done_actions)
        if not asyncio.run(load_snapshot(self.initial_snapshot)):
            logger.error("Error in loading snapshot")
            return []
        initial_layout = asyncio.run(capture_layout())
        asyncio.run(save_screenshot(self.device, str(self.writer.explore_supp_path.joinpath(f"INITIAL.png"))))
        stb_result_list = {}
        all_activity_names = []
        is_in_app_activity = not asyncio.run(is_android_activity_on_top())
        if is_in_app_activity:
            for index, action in enumerate(tb_undone_actions):
                if not asyncio.run(load_snapshot(self.initial_snapshot)):
                    logger.error("Error in loading snapshot")
                    return []
                reg_layout, reg_result = asyncio.run(reg_execute_command(json.dumps(action)))
                if reg_layout == initial_layout or reg_result.state != 'COMPLETED':  # the action is not meaningful
                    continue
                self.writer.capture_current_state(self.device, f"M_{index}", reg_layout, "reg")
                all_activity_names.append(f"REG_C $ {index} $ {asyncio.run(get_current_activity_name())}")
                annotate_rectangle(self.writer.explore_supp_path.joinpath(f"INITIAL.png"),
                                   self.writer.explore_supp_path.joinpath(f"I_{index}_R.png"),
                                   reg_result.bound,
                                   outline=(255, 0, 255),
                                   width=5,
                                   scale=1)
                if not asyncio.run(load_snapshot(self.initial_snapshot)):
                    logger.error("Error in loading snapshot")
                    return []
                stb_layout, stb_result = asyncio.run(stb_execute_command(json.dumps(action)))
                self.writer.capture_current_state(self.device, f"M_{index}", stb_layout, "tb")
                all_activity_names.append(f"STB_C $ {index} $ {asyncio.run(get_current_activity_name())}")
                annotate_rectangle(self.writer.explore_supp_path.joinpath(f"I_{index}_R.png"),
                                   self.writer.explore_supp_path.joinpath(f"I_{index}_RS.png"),
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
        with open(self.writer.stb_result_path, "w") as f:
            json.dump(stb_result_list, f)
        with open(str(self.writer.stb_result_path.absolute()) + "_activities.txt", "w") as f:
            f.writelines(all_activity_names)

    def report_issues(self):
        different_behaviors = []
        directional_unreachable = []
        unlocatable = []
        different_behaviors_directional_unreachable = []
        tb_xpaths = {}
        pending = False
        if self.writer.explore_result_path.exists():
            with open(self.writer.explore_result_path) as f:
                explore_result = json.load(f)
                for index in explore_result:
                    tb_xpaths[explore_result[index]['command']['xpath']] = explore_result[index]['command']
                    if not explore_result[index]['same']:
                        different_behaviors.append(explore_result[index]['command'])
        else:
            pending = True

        if self.writer.stb_result_path.exists():
            with open(self.writer.stb_result_path) as f:
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
