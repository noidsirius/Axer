import asyncio
import json
import logging
import shutil
import tempfile
from abc import ABC, abstractmethod
from typing import Union

from ppadb.device_async import DeviceAsync

from GUI_utils import Node
from a11y_service import A11yServiceManager
from adb_utils import read_local_android_file
from command import Command, CommandResponse, create_command_response_from_dict, SleepCommand, InfoCommand, \
    LocatableCommand, ClickCommand, TypeCommand, SelectCommand
from consts import ACTION_EXECUTION_RETRY_COUNT, REGULAR_EXECUTE_TIMEOUT_TIME, DEVICE_NAME
from latte_executor_utils import latte_capture_layout
from latte_utils import send_commands_sequence_to_latte, send_command_to_latte
from results_utils import AddressBook, capture_current_state
from shell_utils import run_bash
from snapshot import DeviceSnapshot

logger = logging.getLogger(__name__)


class Controller(ABC):
    CONTROLLER_RESULT_FILE_NAME = "controller_result.txt"

    def __init__(self, device: DeviceAsync):
        self.device = device

    def name(self) -> str:
        return type(self).__name__

    @abstractmethod
    def mode(self) -> str:
        return 'base'

    @abstractmethod
    async def setup(self):
        pass

    async def execute(self, command: Command, first_setup: bool = False, **kwargs) -> CommandResponse:
        if isinstance(command, SleepCommand):
            if command.delay > 0:
                logger.info(f"Sleeping for {command.delay}ms!")
                await asyncio.sleep(command.delay / 1000)
                return CommandResponse(command_type='SleepCommand', state='COMPLETED', duration=command.delay)
            logger.info(f"The delay is invalid: {command.delay}")
            return CommandResponse(command_type='SleepCommand', state='FAILED', duration=0)

        if first_setup:
            await self.setup()
        result = {}
        for i in range(ACTION_EXECUTION_RETRY_COUNT):
            if i > 0:
                await self.setup()
            logger.debug(f"Execute Command using controller {self.name()}, Try: {i}")
            await send_command_to_latte(command="controller_execute",
                                        extra=command.toJSONStr(),
                                        device_name=self.device.serial)
            result = await read_local_android_file(Controller.CONTROLLER_RESULT_FILE_NAME,
                                                   wait_time=REGULAR_EXECUTE_TIMEOUT_TIME,
                                                   device_name=self.device.serial)
            if result is None or len(result.strip()) == 0:
                logger.warning(f"Timeout, skipping {command} for controller {self.name()}")
                result = {'state': 'timeout'}
                await send_command_to_latte("controller_interrupt", device_name=self.device.serial)
            else:
                try:
                    result = json.loads(result)
                except Exception as e:
                    logger.error(f"Problem with json loading the result of execution! Result: {result}, Exception: {e}")
                    result = None
                break
        if result is None:
            result = {'state': 'maxed_retry'}
        response = create_command_response_from_dict(command, result)
        return response


class TouchController(Controller):
    @classmethod
    def mode(cls) -> str:
        return 'touch'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=False, device_name=self.device.serial)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device.serial)


class EnlargedDisplayController(TouchController):
    @classmethod
    def mode(cls) -> str:
        return 'enlarged'

    async def setup(self):
        await super().setup()
        await run_bash(f"adb -s {self.device.serial} shell wm density 546")
        await run_bash(f"adb -s {self.device.serial} shell settings put system font_scale 1.3")


class A11yAPIController(Controller):
    @classmethod
    def mode(cls) -> str:
        return 'a11y_api'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=False, device_name=self.device.serial)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device.serial)


class TalkBackAPIController(Controller):
    @classmethod
    def mode(cls) -> str:
        return 'tb_api'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device.serial)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device.serial)


class TalkBackTouchController(Controller):
    @classmethod
    def mode(cls) -> str:
        return 'tb_touch'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device.serial)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device.serial)


class TalkBackDirectionalController(Controller):
    @classmethod
    def mode(cls) -> str:
        return 'tb_dir'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device.serial)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device.serial)


class TalkBackJumpController(Controller):
    @classmethod
    def mode(cls) -> str:
        return 'tb_jump'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device.serial)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device.serial)


class TalkBackSearchController(Controller):
    SEARCH_BOX_NODE = '{"bounds": [384, 63, 954, 189],' \
                      '"class_name": "android.widget.EditText",' \
                      '"resource_id": "com.google.android.marvin.talkback:id/keyword_edit", ' \
                      '"text": "Search term", ' \
                      '"xpath": "/android.widget.LinearLayout/android.widget.RelativeLayout/android.widget.EditText"}'

    CLOSE_NODE = '{"bounds": [0, 63, 126, 189], ' \
                 '"class_name": "android.widget.ImageButton", ' \
                 '"content_desc": "Close search", ' \
                 '"resource_id": "com.google.android.marvin.talkback:id/cancel_search", ' \
                 '"xpath": "/android.widget.LinearLayout/android.widget.RelativeLayout/android.widget.ImageButton[1]"}'

    @classmethod
    def mode(cls) -> str:
        return 'tb_search'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device.serial)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device.serial)

    async def _make_tmp_device_snapshot(self) -> DeviceSnapshot:
        temp_dir = tempfile.mkdtemp()
        address_book = AddressBook(snapshot_result_path=temp_dir)
        snapshot = DeviceSnapshot(address_book=address_book, device=self.device)
        await snapshot.setup(enabled_assistive_services=["tb"])
        shutil.rmtree(temp_dir)
        return snapshot

    async def execute(self, command: Command, first_setup: bool = False,
                      address_book: AddressBook = None, **kwargs) -> CommandResponse:
        if not isinstance(command, ClickCommand):
            return await super().execute(command=command, first_setup=first_setup)
        logger.info(f"In TalkBackSearch, clicking on {command.target}")
        await self.setup()
        snapshot = await self._make_tmp_device_snapshot()
        text_description_list = snapshot.get_text_description(command.target)
        text_word_list = []
        for text in text_description_list:
            for word in text.strip().split():
                text_word_list.append(word)
        if len(text_description_list) == 0 or len("".join(text_description_list)) == 0:
            logger.error("The target node does not have any text description")
            return CommandResponse(command_type=command.name(), state="FAILED_NO_TEXT", duration=1)
        # Open Search Screen
        await send_command_to_latte(command="tb_search", device_name=self.device.serial)
        logger.info(f"TalkBack Search for word '{text_word_list[0]}, "
                    f"the full text description '{' - '.join(text_description_list)}'")
        type_command = TypeCommand(target=Node.createNodeFromDict(json.loads(TalkBackSearchController.SEARCH_BOX_NODE)),
                                   text=text_word_list[0])
        type_response = await super().execute(command=type_command)
        logger.info(f"Type Response: {type_response}")
        await asyncio.sleep(1)
        # Find a candidate to click
        snapshot = await self._make_tmp_device_snapshot()
        if address_book is not None:
            await capture_current_state(address_book,
                                        self.device,
                                        mode=AddressBook.BASE_MODE,
                                        index="SEARCH",
                                        has_layout=True,
                                        use_adb_layout=False)
        max_common_words = (None, 0)
        text_word_set = set(text_word_list)
        for node in snapshot.nodes:
            if node.resource_id == type_command.target.resource_id:
                continue
            text = node.text.strip()
            words = set(text.split())
            if len(words) > 0:
                logger.info(f"Candidate: {text}, '{words}', '{text_word_set}'")
                common_words = len(words.intersection(text_word_set))
                if common_words > max_common_words[1]:
                    max_common_words = (node, common_words)
        if max_common_words[0] is None:
            logger.error("No candidate found for search!")
            return CommandResponse(command_type=command.name(), state="FAILED_NO_ENTRY", duration=1)
        # Click the candidate
        candidate_node: Node = max_common_words[0]
        logger.info(f"The candidate is {candidate_node}")
        talkback_api_controller = TalkBackAPIController(device=self.device)
        click_command = ClickCommand(target=candidate_node)
        click_response = await talkback_api_controller.execute(command=click_command, first_setup=True)
        logger.info(f"Click Response: {click_response}")
        # Check if the focused node is the target
        info_response = await super().execute(InfoCommand(question="is_focused", extra=command.target.toJSON()))
        logger.info(f"Info Response: {info_response}")
        target_is_focused = False
        try:
            result = info_response.answer
            target_is_focused = result.get('result', False) if result else False
        except Exception as e:
            pass

        # Clicking on the target node
        if target_is_focused:
            logger.info(f"The target node is focused!")
            return await talkback_api_controller.execute(SelectCommand())
        return CommandResponse(command_type=command.name(), state="FAILED_LOCATE", duration=1)


def create_controller(mode: str, device: DeviceAsync) -> Union[Controller, None]:
    controllers = [TalkBackTouchController, TalkBackDirectionalController, TalkBackJumpController,
                   TalkBackSearchController, TalkBackAPIController, A11yAPIController, TouchController,
                   EnlargedDisplayController]
    for controller in controllers:
        if mode == controller.mode():
            return controller(device=device)
    return None
