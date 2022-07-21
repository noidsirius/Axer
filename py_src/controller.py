import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Union

from a11y_service import A11yServiceManager
from adb_utils import read_local_android_file
from command import Command, CommandResponse, create_command_response_from_dict, SleepCommand
from consts import ACTION_EXECUTION_RETRY_COUNT, REGULAR_EXECUTE_TIMEOUT_TIME, DEVICE_NAME
from latte_utils import send_commands_sequence_to_latte, send_command_to_latte

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
                await asyncio.sleep(command.delay/1000)
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
            if result is None:
                logger.warning(f"Timeout, skipping {command} for controller {self.name()}")
                result = {'state': 'timeout'}
                await send_command_to_latte("controller_interrupt", device_name=self.device_name)
            else:
                result = json.loads(result)
                break
        if result is None:
            result = {'state': 'maxed_retry'}
        response = create_command_response_from_dict(command, result)
        return response


class TouchController(Controller):
    def mode(self) -> str:
        return 'touch'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=False, device_name=self.device_name)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device_name)


class A11yAPIController(Controller):
    def mode(self) -> str:
        return 'a11y_api'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=False, device_name=self.device_name)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device_name)


class TalkBackAPIController(Controller):
    def mode(self) -> str:
        return 'tb_api'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device_name)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device_name)


class TalkBackTouchController(Controller):
    def mode(self) -> str:
        return 'tb_touch'

    async def setup(self):
        await A11yServiceManager.setup_latte_a11y_services(tb=True, device_name=self.device_name)
        await send_commands_sequence_to_latte([("controller_set", self.mode())], device_name=self.device_name)


def create_controller(mode: str, device_name: str) -> Union[Controller, None]:
    if mode == 'tb_touch':
        return TalkBackTouchController(device_name=device_name)
    elif mode == 'tb_api':
        return TalkBackAPIController(device_name=device_name)
    elif mode == 'a11y_api':
        return A11yAPIController(device_name=device_name)
    elif mode == 'touch':
        return TouchController(device_name=device_name)
    return None