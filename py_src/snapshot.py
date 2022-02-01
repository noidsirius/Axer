import logging
import asyncio
import json
from collections import defaultdict
from typing import Callable, List, Tuple, Union
from ppadb.client_async import ClientAsync as AdbClient

from GUI_utils import get_elements, are_equal_elements
from a11y_service import A11yServiceManager
from adb_utils import load_snapshot, save_snapshot, is_android_activity_on_top, get_current_activity_name
from latte_utils import latte_capture_layout as capture_layout
from latte_utils import talkback_nav_command, tb_navigate_next, tb_perform_select, \
    reg_execute_command, stb_execute_command, get_missing_actions
from padb_utils import ParallelADBLogger
from results_utils import AddressBook, ResultWriter
from consts import EXPLORE_VISIT_LIMIT

logger = logging.getLogger(__name__)


class Snapshot:
    def __init__(self,
                 snapshot_name: str,
                 address_book: AddressBook,
                 visited_elements_in_app: dict = None,
                 client: AdbClient = None,
                 device_name: str = "emulator-5554"):
        self.initial_snapshot = snapshot_name
        self.tmp_snapshot = self.initial_snapshot + "_TMP"
        self.address_book = address_book
        self.writer = ResultWriter(address_book)
        self.visited_elements_in_app = {} if visited_elements_in_app is None else visited_elements_in_app
        # -------------
        self.visible_elements = []
        self.valid_resource_ids = set()
        self.valid_xpaths = {}
        self.visited_resource_ids = set()
        self.visited_xpath_count = defaultdict(int)
        self.tb_commands = []
        # -------------
        if client is None:
            client = AdbClient(host="127.0.0.1", port=5037)
        self.device = asyncio.run(client.device(device_name))

    async def emulator_setup(self) -> bool:
        """
        Loads the snapshot into emulator, configures the required services, and sets up Latte.
        Then saves the configured snapshot into Temp Snapshot.
        Finally it analyzes all elements in the screen and exclude the already seen (in other snapshots)
        :return: Whether the setup is succeeded or not
        """
        if not await load_snapshot(self.initial_snapshot):
            logger.error("Error in loading snapshot")
            return False
        if await is_android_activity_on_top():
            logger.error("The snapshot is broken!")
            return False
        await A11yServiceManager.setup_latte_a11y_services(tb=True)
        await talkback_nav_command("clear_history")
        logger.info("Enabled A11y Services:" + str(await A11yServiceManager.get_enabled_services()))
        await asyncio.sleep(3)
        await save_snapshot(self.tmp_snapshot)
        # ------------- TODO: think about it later ----------
        dom = await capture_layout()
        self.visible_elements = get_elements(dom)
        self.valid_resource_ids = set()
        self.valid_xpaths = {}
        already_visited_elements = []
        for element in self.visible_elements:
            has_been_in_other_snapshots = False
            for other_element in self.visited_elements_in_app.get(element['xpath'], []):
                if 'detailed_element' in other_element:
                    detailed_element = other_element['detailed_element']
                    if detailed_element is not None:
                        if are_equal_elements(element, detailed_element):
                            logger.debug(f"Exclude the visited element in the app {element}")
                            has_been_in_other_snapshots = True
                            break
                else:
                    logger.warning(f"No 'detailed_element' key in {self.visited_elements_in_app[element['xpath']]}")
            if has_been_in_other_snapshots:
                already_visited_elements.append(element)
                continue
            if element['resourceId']:
                self.valid_resource_ids.add(element['resourceId'])
            if element['xpath']:
                self.valid_xpaths[element['xpath']] = element
        logger.info(f"There are {len(self.valid_xpaths)} valid elements,"
                    f" and {len(already_visited_elements)} elements have been seen in other snapshots!")
        self.visited_resource_ids = set()
        self.visited_xpath_count = defaultdict(int)
        self.tb_commands = []
        # -------------
        return True

    async def navigate_next(self, padb_logger: ParallelADBLogger) -> Tuple[str, Union[str, None]]:
        """
        Loads the Temp Sanpshot (latest snapshot in navigation), navigate to next element by TalkBack until it either
        reaches a new important element or finishes the navigation. An important element should belong to the initial
        snapshot, should not have been visited before in this or other snapshots.
        :param padb_logger: To capture the logs of Latte during TalkBack navigation
        :return: A tuple of
                'Log Message' (the logs during the navigation) and
                'Next Command' (the newly focused element). If Next Command is None, the navigation is finished.
        """
        if not await load_snapshot(self.tmp_snapshot):
            logger.debug("Error in loading snapshot")
            return "The snapshot could not be loaded!", None
        while True:
            log_message, next_command_str = await padb_logger.execute_async_with_log(tb_navigate_next())
            if next_command_str is None:
                logger.error("TalkBack cannot navigate to the next element")
                return log_message, None
            command_json = json.loads(next_command_str)
            if command_json['xpath'] != 'null':
                self.visited_xpath_count[command_json['xpath']] += 1
                if self.visited_xpath_count[command_json['xpath']] > EXPLORE_VISIT_LIMIT:
                    logger.info(
                        f"The XPath {command_json['xpath']}"
                        f" is visited more than {EXPLORE_VISIT_LIMIT} times, break. ")
                    return log_message, None
            else:
                logger.error(f"The xpath is null for element {command_json}")
            # TODO: Update visited* with next_command_json
            # TODO: Skip if the position is also the same
            if command_json['xpath'] not in self.valid_xpaths:
                self.writer.visit_element(command_json, 'skipped', None)
                logger.info("Not a valid xpath!")
                continue
            if next_command_str in self.tb_commands:
                self.writer.visit_element(command_json, 'repetitive', self.valid_xpaths[command_json['xpath']])
                logger.info("Has seen this command before!")
                continue
            if command_json['resourceId'] in self.visited_resource_ids:
                self.writer.visit_element(command_json, 'repetitive', self.valid_xpaths[command_json['xpath']])
                logger.info("Has seen this resourceId")
                continue
            if self.visited_xpath_count[command_json['xpath']] > 1:  # TODO: Configurable
                self.writer.visit_element(command_json, 'repetitive', self.valid_xpaths[command_json['xpath']])
                logger.info("Has seen this xpath more than twice")
                continue
            self.writer.visit_element(command_json, 'selected', self.valid_xpaths[command_json['xpath']])
        # TODO: make it a counter
            if command_json['resourceId'] != 'null':
                self.visited_resource_ids.add(command_json['resourceId'])
            break
        return log_message, next_command_str

    async def explore(self) -> bool:
        if not await self.emulator_setup():
            logger.error("Error in emulator setup!")
            return False
        initial_layout = await capture_layout()
        self.writer.start_explore()
        padb_logger = ParallelADBLogger(self.device)
        while True:
            if await is_android_activity_on_top():
                logger.info("We are not in the app under test!")
                self.writer.write_last_navigate_log(f"The current activity is {await get_current_activity_name()}")
                break
            logger.info(f"Action Index: {self.writer.get_action_index()}")
            # ------------------- Navigate Next -------------------
            tb_navigate_log, click_command_str = await self.navigate_next(padb_logger)
            if not click_command_str:
                logger.info("Navigation is finished!")
                self.writer.write_last_navigate_log(tb_navigate_log)
                break
            logger.debug("Click Command is " + click_command_str)
            await self.writer.capture_current_state(self.device, mode="exp",
                                                    index=self.writer.get_action_index(),
                                                    log_message=tb_navigate_log,
                                                    has_layout=False)
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
            tb_layout = await self.writer.capture_current_state(self.device,
                                                                mode="tb",
                                                                index=self.writer.get_action_index(),
                                                                log_message=log_message)
            # ------------------- End TalkBack Select ---------------
            # ------------------- Start Regular Select ---------------
            if not await load_snapshot(self.tmp_snapshot):
                logger.error("Error in loading snapshot")
                return False
            logger.info("Now with regular executor")
            log_message, reg_result = await padb_logger.execute_async_with_log(reg_execute_command(click_command_str))
            reg_layout = await self.writer.capture_current_state(self.device,
                                                                 mode="reg",
                                                                 index=self.writer.get_action_index(),
                                                                 log_message=log_message)
            # ------------------- End Regular Select ---------------
            self.writer.add_action(element=json.loads(click_command_str),
                                   tb_action_result=tb_result,
                                   reg_action_result=reg_result)
            logger.info("Groundhug Day!")
        logger.info("Done Exploring!")
        return True

    async def get_important_actions(self) -> List:
        if not await load_snapshot(self.initial_snapshot):
            logger.error("Error in loading snapshot")
            return []
        dom = await capture_layout()
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

    async def get_meaningful_actions(self, action_list: List, executor: Callable = reg_execute_command) -> List:
        if not await load_snapshot(self.initial_snapshot):
            logger.error("Error in loading snapshot")
            return []
        original_layout = await capture_layout()
        meaningful_actions = []
        for action in action_list:
            if not await load_snapshot(self.initial_snapshot):
                logger.error("Error in loading snapshot")
                return []
            reg_layout, result = await executor(json.dumps(action))
            if reg_layout != original_layout:
                meaningful_actions.append(action)
        return meaningful_actions

    async def validate_by_stb(self):
        logger.info("Validating remaining actions.")
        self.writer.start_stb()
        important_actions = await self.get_important_actions()
        tb_done_actions = self.get_tb_done_actions()
        tb_undone_actions = get_missing_actions(important_actions, tb_done_actions)
        logger.info(f"There are {len(tb_undone_actions)} missing actions in explore!")
        if not await load_snapshot(self.initial_snapshot):
            logger.error("Error in loading snapshot")
            return []
        await asyncio.sleep(2)
        initial_layout = await self.writer.capture_current_state(self.device, 's_exp', 'INITIAL')
        is_in_app_activity = not await is_android_activity_on_top()
        if is_in_app_activity:
            for index, action in enumerate(tb_undone_actions):
                logger.info(f"Missing action {self.writer.get_action_index()}")
                if not await load_snapshot(self.initial_snapshot):
                    logger.error("Error in loading snapshot")
                    return []
                reg_result = await reg_execute_command(json.dumps(action))
                reg_layout = await self.writer.capture_current_state(self.device, "s_reg", self.writer.get_action_index())
                if reg_layout == initial_layout or reg_result.state != 'COMPLETED':  # the action is not meaningful
                    continue

                if not await load_snapshot(self.initial_snapshot):
                    logger.error("Error in loading snapshot")
                    return []

                stb_result = await stb_execute_command(json.dumps(action))
                stb_layout = await self.writer.capture_current_state(self.device, "s_tb", self.writer.get_action_index())

                logger.info(f"Writing action {self.writer.get_action_index()}")
                self.writer.add_action(action, stb_result, reg_result, is_sighted=True)
        logger.info("Done validating remaining actions.")
