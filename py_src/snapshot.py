import logging
import asyncio
import json
from collections import defaultdict
from typing import List, Tuple, Union
from ppadb.client_async import ClientAsync as AdbClient

from GUI_utils import get_elements, are_equal_elements, get_actions_from_layout, is_clickable_element_or_none, \
    get_element_from_xpath
from a11y_service import A11yServiceManager
from adb_utils import load_snapshot, save_snapshot, is_android_activity_on_top, get_current_activity_name
from latte_executor_utils import tb_navigate_next, tb_perform_select, tb_focused_node, execute_command, \
    get_missing_actions, latte_capture_layout as capture_layout, report_atf_issues
from padb_utils import ParallelADBLogger
from results_utils import AddressBook, ResultWriter
from utils import annotate_elements
from consts import EXPLORE_VISIT_LIMIT, DEVICE_NAME, ADB_HOST, ADB_PORT, BLIND_MONKEY_TAG, \
    BLIND_MONKEY_INSTRUMENTED_TAG, BLIND_MONKEY_EVENTS_TAG

logger = logging.getLogger(__name__)


class Snapshot:
    def __init__(self,
                 snapshot_name: str,
                 address_book: AddressBook,
                 visited_elements_in_app: dict = None,
                 instrumented_log: bool = False,
                 action_limit: int = 1000,
                 device=None):
        self.initial_snapshot = snapshot_name
        self.tmp_snapshot = self.initial_snapshot + "_TMP"
        self.action_limit = action_limit
        self.address_book = address_book
        self.instrumented_log = instrumented_log
        self.writer = ResultWriter(address_book)
        self.visited_elements_in_app = {} if visited_elements_in_app is None else visited_elements_in_app
        # -------------
        self.init_layout = None
        self.visible_elements = []
        self.valid_resource_ids = set()
        self.valid_xpaths = {}
        self.visited_resource_ids = set()
        self.visited_xpath_count = defaultdict(int)
        self.performed_actions = []
        # -------------
        if device is None:
            client = AdbClient(host=ADB_HOST, port=ADB_PORT)
            device = asyncio.run(client.device(DEVICE_NAME))
        self.device = device

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
        Finally, it analyzes all elements in the screen and exclude the already seen (in other snapshots)
        :return: Whether the setup is succeeded or not
        """
        if not await load_snapshot(self.initial_snapshot, device_name=self.device.serial):
            logger.error("Error in loading snapshot")
            return False
        if await is_android_activity_on_top(device_name=self.device.serial):
            logger.error("The snapshot is broken!")
            return False
        await A11yServiceManager.setup_latte_a11y_services(tb=True)
        logger.info("Enabled A11y Services:" + str(await A11yServiceManager.get_enabled_services()))
        await asyncio.sleep(3)
        await save_snapshot(self.tmp_snapshot)
        self.writer.start_explore()
        # ------------- TODO: think about it later ----------
        # dom = await capture_layout()

        self.init_layout = await self.writer.capture_current_state(self.device, mode="exp", index="INITIAL",
                                                                   has_layout=True)
        atf_issues = await report_atf_issues()
        logger.info(f"There are {len(atf_issues)} ATF issues in this screen!")
        with open(self.address_book.atf_issues_path, "w") as f:
            for issue in atf_issues:
                f.write(json.dumps(issue) + "\n")
        annotate_elements(self.address_book.get_screenshot_path('exp', 'INITIAL'),
                          self.address_book.atf_issues_screenshot,
                          atf_issues)
        self.visible_elements = get_elements(self.init_layout)
        annotate_elements(self.address_book.get_screenshot_path('exp', 'INITIAL'),
                          self.address_book.all_element_screenshot,
                          self.visible_elements)
        annotate_elements(self.address_book.get_screenshot_path('exp', 'INITIAL'),
                          self.address_book.all_action_screenshot,
                          get_actions_from_layout(self.init_layout),
                          outline=(138, 43, 226),
                          width=15)
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
                          already_visited_elements)
        annotate_elements(self.address_book.get_screenshot_path('exp', 'INITIAL'),
                          self.address_book.valid_action_screenshot,
                          list(self.valid_xpaths.values()))
        logger.info(f"There are {len(self.valid_xpaths)} valid elements,"
                    f" and {len(already_visited_elements)} elements have been seen in other snapshots!")
        with open(self.address_book.valid_elements_path, "w") as f:
            for valid_element in self.valid_xpaths.values():
                f.write(f"{json.dumps(valid_element)}\n")
        self.visited_resource_ids = set()
        self.visited_xpath_count = defaultdict(int)
        self.performed_actions = []
        # -------------
        return True

    async def navigate_next(self, padb_logger: ParallelADBLogger) -> Tuple[str, Union[str, None]]:
        """
        Loads the tmp Snapshot (the latest snapshot in navigation), navigate to next element by TalkBack until it either
        reaches a new important element or finishes the navigation. An important element should belong to the initial
        snapshot, should not have been visited before in this or other snapshots.

        :param: padb_logger: To capture the logs of Latte during TalkBack navigation
        :return: A tuple of
                'Log Message' (the logs during the navigation) and
                'Next Command' (the newly focused element). If Next Command is None, the navigation is finished.
        """
        logger.info("Navigating to the next element")
        if not await load_snapshot(self.tmp_snapshot):
            logger.debug("Error in loading snapshot")
            return "The snapshot could not be loaded!", None
        all_log_message = ""
        tags = [BLIND_MONKEY_TAG]
        if self.instrumented_log:
            tags.append(BLIND_MONKEY_INSTRUMENTED_TAG)

        while True:
            log_message_map, next_command_str = await padb_logger.execute_async_with_log(tb_navigate_next(), tags=tags)
            if len(tags) == 1:
                all_log_message += list(log_message_map.values())[0]
            else:
                all_log_message += "".join(f"---Start {key}-----\n"
                                           f"{value}\n"
                                           f"----End {key}----\n"
                                           for (key, value) in log_message_map.items())
            if not next_command_str or next_command_str == "Error":
                logger.error("TalkBack cannot navigate to the next element")
                return all_log_message, None
            if await is_android_activity_on_top():
                logger.info("We are not in the app under test!")
                return f"The current activity is {await get_current_activity_name()}", None
            command_json = json.loads(next_command_str)
            logger.debug(f"Current element: {command_json}")
            if command_json['xpath'] != 'null':
                self.visited_xpath_count[command_json['xpath']] += 1
                if self.visited_xpath_count[command_json['xpath']] > EXPLORE_VISIT_LIMIT:
                    logger.info(
                        f"The XPath {command_json['xpath']}"
                        f" is visited more than {EXPLORE_VISIT_LIMIT} times, break. ")
                    return all_log_message, None
            else:
                logger.error(f"The xpath is null for element {command_json}")
            # TODO: Update visited* with next_command_json
            # TODO: Skip if the position is also the same
            if command_json['xpath'] not in self.valid_xpaths:
                self.writer.visit_element(command_json, 'skipped', None)
                logger.debug("Not a valid xpath!")
                continue
            if next_command_str in self.performed_actions:
                self.writer.visit_element(command_json, 'repetitive', self.valid_xpaths[command_json['xpath']])
                logger.debug("Has seen this command before!")
                continue
            # if command_json['resourceId'] in self.visited_resource_ids:
            #     self.writer.visit_element(command_json, 'repetitive', self.valid_xpaths[command_json['xpath']])
            #     logger.debug("Has seen this resourceId")
            #     continue
            if self.visited_xpath_count[command_json['xpath']] > 1:  # TODO: Configurable
                self.writer.visit_element(command_json, 'repetitive', self.valid_xpaths[command_json['xpath']])
                logger.debug("Has seen this xpath more than twice")
                continue
            if not is_clickable_element_or_none(self.init_layout, command_json['xpath']):
                self.writer.visit_element(command_json, 'unclickable', self.valid_xpaths[command_json['xpath']])
                logger.debug("The element is not clickable!")
                continue
            self.writer.visit_element(command_json, 'selected', self.valid_xpaths[command_json['xpath']])
            # TODO: make it a counter
            if command_json['resourceId'] != 'null':
                self.visited_resource_ids.add(command_json['resourceId'])
            break
        return all_log_message, next_command_str

    async def explore(self) -> bool:
        if not await self.emulator_setup():
            logger.error("Error in emulator setup!")
            return False
        padb_logger = ParallelADBLogger(self.device)
        await self.writer.capture_current_state(self.device, mode="exp",
                                                index=self.writer.get_action_index(),
                                                log_message_map={BLIND_MONKEY_TAG: "First State"},
                                                has_layout=True)
        next_focused_element = None
        while True:
            if len(self.performed_actions) >= self.action_limit:
                logger.info(f"Reached action limit: {self.action_limit}")
                break
            logger.info(f"Action Index: {self.writer.get_action_index()}")
            await save_snapshot(self.tmp_snapshot)
            click_command_str = await tb_focused_node()

            if not click_command_str or click_command_str == 'Error':
                logger.error(f"The focused node is None, expected focused node: {next_focused_element}")
            else:
                click_command = json.loads(click_command_str)
                if not is_clickable_element_or_none(self.init_layout, click_command['xpath']):
                    logger.info(f"The focused node is not clickable, Action: {click_command}")
                else:
                    if click_command_str != next_focused_element and next_focused_element is not None:
                        logger.error(f"The current focused element is different from the navigation's result."
                                     f"Current: {click_command_str}, NextFocusedElement: {next_focused_element}")
                    self.performed_actions.append(click_command_str)
                    modes = ['tb', 'reg', 'areg']
                    result_map = {}
                    for mode in modes:
                        logger.info(f"Executing select in Mode: {mode}")
                        tags = [BLIND_MONKEY_TAG, BLIND_MONKEY_EVENTS_TAG]
                        if self.instrumented_log:
                            tags.append(BLIND_MONKEY_INSTRUMENTED_TAG)
                        if mode != 'tb':
                            if not await load_snapshot(self.initial_snapshot):
                                logger.error("Error in loading snapshot")
                                return False
                            log_message_map, result_map[mode] = await padb_logger.execute_async_with_log(
                                execute_command(click_command_str, executor_name=mode),
                                tags=tags)
                        else:
                            log_message_map, result_map[mode] = await padb_logger.execute_async_with_log(
                                tb_perform_select(),
                                tags=tags)
                        layout = await self.writer.capture_current_state(self.device, mode,
                                                                         self.writer.get_action_index(),
                                                                         log_message_map=log_message_map)
                    # ------------------- Add action to results ---------------
                    self.writer.add_action(element=click_command,
                                           tb_action_result=result_map['tb'],
                                           reg_action_result=result_map['reg'],
                                           areg_action_result=result_map.get('areg', None),
                                           detailed_element=self.valid_xpaths.get(click_command['xpath'], None),
                                           is_sighted=False)

            # ------------------- Navigate Next -------------------
            tb_navigate_log, next_focused_element = await self.navigate_next(padb_logger)
            if not next_focused_element:
                logger.info("Navigation is finished!")
                self.writer.write_last_navigate_log(tb_navigate_log)
                break
            logger.debug("Next focused element is " + next_focused_element)
            await self.writer.capture_current_state(self.device, mode="exp",
                                                    index=self.writer.get_action_index(),
                                                    log_message_map={BLIND_MONKEY_TAG: tb_navigate_log},
                                                    has_layout=True)
            # ------------------- End Navigate Next -------------------
            logger.info("Groundhog Day!")

        annotate_elements(self.address_book.get_screenshot_path('exp', 'INITIAL'),
                          self.address_book.visited_action_screenshot,
                          [json.loads(str_command) for str_command in self.performed_actions])
        annotate_elements(self.address_book.get_screenshot_path('exp', 'INITIAL'),
                          self.address_book.visited_elements_screenshot,
                          [visited_element['detailed_element'] for visited_element in self.writer.visited_elements])
        logger.info("Done Exploring!")
        return True

    async def get_important_actions(self) -> List:
        if not await load_snapshot(self.initial_snapshot):
            logger.error("Error in loading snapshot")
            return []
        await asyncio.sleep(2)
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
        important_actions = await self.get_important_actions()
        tb_done_actions = self.get_tb_done_actions()
        directional_unreachable_actions = get_missing_actions(important_actions, tb_done_actions)
        logger.info(f"There are {len(directional_unreachable_actions)} missing actions in explore!")
        initial_layout = await self.writer.capture_current_state(self.device, 's_exp', 'INITIAL')
        annotate_elements(self.address_book.get_screenshot_path('s_exp', 'INITIAL'),
                          self.address_book.s_action_screenshot,
                          directional_unreachable_actions)
        is_in_app_activity = not await is_android_activity_on_top()
        padb_logger = ParallelADBLogger(self.device)
        if is_in_app_activity:
            for index, action in enumerate(directional_unreachable_actions):
                if len(self.performed_actions) + self.writer.get_action_index() >= self.action_limit:
                    logger.info(f"Reached action limit: {self.action_limit}")
                    break
                logger.info(
                    f"Missing action {self.writer.get_action_index()}, count: {index} / {len(directional_unreachable_actions)}")
                if get_element_from_xpath(initial_layout, action['xpath']) is None:
                    continue
                result_map = {}
                modes = ['reg', 'areg', 'tb']
                tags = [BLIND_MONKEY_TAG, BLIND_MONKEY_EVENTS_TAG]
                if self.instrumented_log:
                    tags.append(BLIND_MONKEY_INSTRUMENTED_TAG)
                for mode in modes:
                    if not await load_snapshot(self.initial_snapshot):
                        logger.error("Error in loading snapshot")
                        return []
                    executor = mode if mode != 'tb' else 'stb'
                    log_message_map, result_map[mode] = await padb_logger.execute_async_with_log(
                        execute_command(json.dumps(action), executor_name=executor), tags=tags)
                    layout = await self.writer.capture_current_state(self.device, f"s_{mode}",
                                                                     self.writer.get_action_index(),
                                                                     log_message_map=log_message_map)

                logger.info(f"Writing action {self.writer.get_action_index()}")
                self.writer.add_action(element=action,
                                       tb_action_result=result_map['tb'],
                                       reg_action_result=result_map['reg'],
                                       areg_action_result=result_map.get('areg', None),
                                       detailed_element=self.valid_xpaths.get(action['xpath'], None),
                                       is_sighted=True)
        logger.info("Done validating remaining actions.")
