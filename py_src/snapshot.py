import logging
import asyncio
import json
from collections import defaultdict
from typing import Callable, List, Tuple, Union
from ppadb.client_async import ClientAsync as AdbClient

from GUI_utils import get_elements, are_equal_elements, get_actions_from_layout
from a11y_service import A11yServiceManager
from adb_utils import load_snapshot, save_snapshot, is_android_activity_on_top, get_current_activity_name
from latte_utils import latte_capture_layout as capture_layout, get_unsuccessful_execution_result
from latte_utils import talkback_nav_command, tb_navigate_next, tb_perform_select, \
    reg_execute_command, stb_execute_command, get_missing_actions
from padb_utils import ParallelADBLogger
from results_utils import AddressBook, ResultWriter
from utils import annotate_elements
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

    def has_element_in_other_snapshots(self, element: dict) -> bool:
        for other_element in self.visited_elements_in_app.get(element['xpath'], []):
            if are_equal_elements(element, other_element):
                logger.debug(f"Exclude the visited element in the app {element}")
                return True
        return False

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
        logger.info("Enabled A11y Services:" + str(await A11yServiceManager.get_enabled_services()))
        await asyncio.sleep(3)
        await save_snapshot(self.tmp_snapshot)
        self.writer.start_explore()
        # ------------- TODO: think about it later ----------
        # dom = await capture_layout()
        layout = await self.writer.capture_current_state(self.device, mode="exp", index="INITIAL", has_layout=True)
        self.visible_elements = get_elements(layout)
        annotate_elements(self.address_book.get_screenshot_path('exp', 'INITIAL'),
                          self.address_book.all_element_screenshot,
                          self.visible_elements,
                          outline=(255, 0, 255),
                          width=10,
                          scale=10)
        annotate_elements(self.address_book.get_screenshot_path('exp', 'INITIAL'),
                          self.address_book.all_action_screenshot,
                          get_actions_from_layout(layout),
                          outline=(255, 0, 255),
                          width=10,
                          scale=10)
        self.valid_resource_ids = set()
        self.valid_xpaths = {}
        already_visited_elements = []
        for element in self.visible_elements:
            if self.has_element_in_other_snapshots(element):
                logger.debug(f"Exclude the visited element in the app {element}")
                already_visited_elements.append(element)
                continue
            if element['resourceId']:
                self.valid_resource_ids.add(element['resourceId'])
            if element['xpath']:
                self.valid_xpaths[element['xpath']] = element
        annotate_elements(self.address_book.get_screenshot_path('exp', 'INITIAL'),
                          self.address_book.redundant_action_screenshot,
                          already_visited_elements,
                          outline=(255, 0, 255),
                          width=10,
                          scale=10)
        annotate_elements(self.address_book.get_screenshot_path('exp', 'INITIAL'),
                          self.address_book.valid_action_screenshot,
                          list(self.valid_xpaths.values()),
                          outline=(255, 0, 255),
                          width=10,
                          scale=10)
        logger.info(f"There are {len(self.valid_xpaths)} valid elements,"
                    f" and {len(already_visited_elements)} elements have been seen in other snapshots!")
        with open(self.address_book.valid_elements_path, "w") as f:
            for valid_element in self.valid_xpaths.values():
                f.write(f"{json.dumps(valid_element)}\n")
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
            logger.debug(f"Current element: {command_json}")
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
        annotate_elements(self.address_book.get_screenshot_path('exp', 'INITIAL'),
                          self.address_book.visited_action_screenshot,
                          [json.loads(str_command) for str_command in self.tb_commands],
                          outline=(255, 0, 255),
                          width=10,
                          scale=10)
        logger.info("Done Exploring!")
        return True

    async def get_important_actions(self) -> List:
        if not await load_snapshot(self.initial_snapshot):
            logger.error("Error in loading snapshot")
            return []
        dom = await capture_layout()
        all_actions = get_actions_from_layout(dom)
        result = []
        for element in all_actions:
            if self.has_element_in_other_snapshots(element):
                logger.debug(f"Sighted: Exclude the visited element in the app {element}")
                continue
            result.append(element)
        return result

    def get_tb_done_actions(self):
        result = []
        explore_result = []
        with open(self.address_book.action_path) as f:
            for line in f.readlines():
                explore_result.append(json.loads(line))
        for action in explore_result:
            result.append(action['element'])
        return result

    async def validate_by_stb(self):
        logger.info("Validating remaining actions.")
        self.writer.start_stb()
        if not await load_snapshot(self.initial_snapshot):
            logger.error("Error in loading snapshot")
            return []
        await asyncio.sleep(2)
        important_actions = await self.get_important_actions()
        tb_done_actions = self.get_tb_done_actions()
        tb_undone_actions = get_missing_actions(important_actions, tb_done_actions)
        logger.info(f"There are {len(tb_undone_actions)} missing actions in explore!")
        initial_layout = await self.writer.capture_current_state(self.device, 's_exp', 'INITIAL')
        annotate_elements(self.address_book.get_screenshot_path('s_exp', 'INITIAL'),
                          self.address_book.s_action_screenshot,
                          tb_undone_actions,
                          outline=(255, 0, 255),
                          width=10,
                          scale=10)
        is_in_app_activity = not await is_android_activity_on_top()
        padb_logger = ParallelADBLogger(self.device)
        if is_in_app_activity:
            for index, action in enumerate(tb_undone_actions):
                logger.info(f"Missing action {self.writer.get_action_index()}, count: {index} / {len(tb_undone_actions)}")
                if not await load_snapshot(self.initial_snapshot):
                    logger.error("Error in loading snapshot")
                    return []
                reg_log_message, reg_result = await padb_logger.execute_async_with_log(reg_execute_command(json.dumps(action)))
                reg_layout = await self.writer.capture_current_state(self.device, "s_reg",
                                                                     self.writer.get_action_index(),
                                                                     log_message=reg_log_message)
                if reg_layout == initial_layout or reg_result.state != 'COMPLETED':  # the action is not meaningful
                    logger.info(f"Writing action {self.writer.get_action_index()}")
                    self.writer.add_action(action, get_unsuccessful_execution_result("UNKNOWN"), reg_result, is_sighted=True)
                    continue

                if not await load_snapshot(self.initial_snapshot):
                    logger.error("Error in loading snapshot")
                    return []

                stb_log_message, stb_result = await padb_logger.execute_async_with_log(stb_execute_command(json.dumps(action)))
                stb_layout = await self.writer.capture_current_state(self.device, "s_tb",
                                                                     self.writer.get_action_index(),
                                                                     log_message=stb_log_message)

                logger.info(f"Writing action {self.writer.get_action_index()}")
                self.writer.add_action(action, stb_result, reg_result, is_sighted=True)
        logger.info("Done validating remaining actions.")
