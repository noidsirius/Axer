import json
import logging

from GUI_utils import Node
from command import ClickCommand, CommandResponse, LocatableCommandResponse, Command
from consts import BLIND_MONKEY_TAG, BLIND_MONKEY_EVENTS_TAG
from controller import TalkBackTouchController, TouchController, A11yAPIController, TalkBackAPIController, Controller
from latte_executor_utils import report_atf_issues
from padb_utils import ParallelADBLogger
from results_utils import AddressBook, Actionables, capture_current_state, ActionResult
from snapshot import EmulatorSnapshot, DeviceSnapshot
from task.snapshot_task import SnapshotTask
from utils import annotate_elements, annotate_rectangle

logger = logging.getLogger(__name__)


class ExecuteSingleActionTask(SnapshotTask):
    def __init__(self, snapshot: DeviceSnapshot, controller: Controller, command: Command):
        if not isinstance(snapshot, DeviceSnapshot):
            raise Exception("ExecuteSingleAction task requires a DeviceSnapshot!")
        if controller.device_name != snapshot.device.serial:
            raise Exception("Controller and DeviceSnapshot should have same device!")
        self.controller = controller
        self.command = command
        super().__init__(snapshot)

    async def execute(self):
        snapshot: DeviceSnapshot = self.snapshot
        device = snapshot.device
        snapshot.address_book.initiate_execute_single_action_task()
        padb_logger = ParallelADBLogger(device)
        tags = [BLIND_MONKEY_TAG, BLIND_MONKEY_EVENTS_TAG]
        logger.info(f"Setup controller {self.controller.name()}")
        await self.controller.setup()
        logger.info(f"Executing command {self.command}")
        result = await padb_logger.execute_async_with_log(
            self.controller.execute(self.command),
            tags=tags)
        log_message_map: dict = result[0]
        action_response: LocatableCommandResponse = result[1]
        logger.info(f"The action is performed in {action_response.duration}ms! State: {action_response.state} ")
        await capture_current_state(snapshot.address_book,
                                    snapshot.device,
                                    mode=self.controller.mode(),
                                    index=0,
                                    log_message_map=log_message_map,
                                    dumpsys=True,
                                    has_layout=True)
        with open(snapshot.address_book.execute_single_action_results_path, "a") as f:
            f.write(f"{action_response.toJSONStr()}\n")
