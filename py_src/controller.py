import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Union

from a11y_service import A11yServiceManager
from adb_utils import read_local_android_file
from command import Command, CommandResponse, create_command_response_from_dict, SleepCommand, InfoCommand, \
    LocatableCommand
from consts import ACTION_EXECUTION_RETRY_COUNT, REGULAR_EXECUTE_TIMEOUT_TIME, DEVICE_NAME
from latte_utils import send_commands_sequence_to_latte, send_command_to_latte
from shell_utils import run_bash
from snapshot import DeviceSnapshot

logger = logging.getLogger(__name__)


class Controller(ABC):
    CONTROLLER_RESULT_FILE_NAME = "controller_result.txt"

    def __init__(self, device_name: str = DEVICE_NAME):
        self.device_name = device_name

    def name(self) -> str:
        return type(self).__name__

    @abstractmethod
    def mode(self) -> str:
        return 'base'

    @abstractmethod
    async def setup(self):
        pass

    async def execute(self, command: Command, first_setup: bool = False) -> CommandResponse:
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
                                        device_name=self.device_name)
            result = await read_local_android_file(Controller.CONTROLLER_RESULT_FILE_NAME,
                                                   wait_time=REGULAR_EXECUTE_TIMEOUT_TIME,
                                                   device_name=self.device_name)
            if result is None or len(result.strip()) == 0:
                logger.warning(f"Timeout, skipping {command} for controller {self.name()}")
                result = {'state': 'timeout'}
                await send_command_to_latte("controller_interrupt", device_name=self.device_name)
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
        await A11yServiceManager.setup_latte_a11y_services(tb=False, device_name=self.device_name)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device_name)


class EnlargedDisplayController(TouchController):
    @classmethod
    def mode(cls) -> str:
        return 'enlarged'

    async def setup(self):
        await super().setup()
        await run_bash(f"adb -s {self.device_name} shell wm density 546")
        await run_bash(f"adb -s {self.device_name} shell settings put system font_scale 1.3")


class A11yAPIController(Controller):
    @classmethod
    def mode(cls) -> str:
        return 'a11y_api'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=False, device_name=self.device_name)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device_name)


class TalkBackAPIController(Controller):
    @classmethod
    def mode(cls) -> str:
        return 'tb_api'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device_name)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device_name)


class TalkBackTouchController(Controller):
    @classmethod
    def mode(cls) -> str:
        return 'tb_touch'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device_name)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device_name)


class TalkBackDirectionalController(Controller):
    @classmethod
    def mode(cls) -> str:
        return 'tb_dir'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device_name)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device_name)


class TalkBackJumpController(Controller):
    @classmethod
    def mode(cls) -> str:
        return 'tb_jump'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device_name)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device_name)


class TalkBackSearchController(Controller):
    SEARCH_BOX_NODE = '{"bounds": [384, 63, 954, 189],' \
                      '"class_name": "android.widget.EditText",' \
                      '"resource_id": "com.google.android.marvin.talkback:id/keyword_edit", ' \
                      '"text": "Search term"' \
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
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device_name)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device_name)

    async def execute(self, command: Command, first_setup: bool = False) -> CommandResponse:
        if not isinstance(command, LocatableCommand):
            return await super().execute(command=command, first_setup=first_setup)



def create_controller(mode: str, device_name: str) -> Union[Controller, None]:
    controllers = [TalkBackTouchController, TalkBackDirectionalController, TalkBackJumpController,
                   TalkBackSearchController, TalkBackAPIController, A11yAPIController, TouchController,
                   EnlargedDisplayController]
    for controller in controllers:
        if mode == controller.mode():
            return controller(device_name=device_name)
    return None
