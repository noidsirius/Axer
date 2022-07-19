import json
import logging

from ppadb.device_async import DeviceAsync

from command import LocatableCommandResponse, Command
from consts import BLIND_MONKEY_TAG, BLIND_MONKEY_EVENTS_TAG
from controller import Controller
from padb_utils import ParallelADBLogger
from results_utils import capture_current_state
from snapshot import Snapshot
from task.snapshot_task import SnapshotTask

logger = logging.getLogger(__name__)


class ExecuteSingleActionTask(SnapshotTask):
    def __init__(self, snapshot: Snapshot, device: DeviceAsync, controller: Controller, command: Command):
        if controller.device_name != device.serial:
            raise Exception("Controller and DeviceSnapshot should have same device!")
        self.controller = controller
        self.device = device
        self.command = command
        super().__init__(snapshot)

    async def execute(self):
        self.snapshot.address_book.initiate_execute_single_action_task()
        padb_logger = ParallelADBLogger(self.device)
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
        await capture_current_state(self.snapshot.address_book,
                                    self.device,
                                    mode=self.controller.mode(),
                                    index=0,
                                    log_message_map=log_message_map,
                                    dumpsys=True,
                                    has_layout=True)
        result = {
            'controller': self.controller.mode(),
            'command': self.command.toJSON(),
            'response': action_response.toJSON(),
        }
        with open(self.snapshot.address_book.execute_single_action_results_path, "w") as f:
            f.write(f"{json.dumps(result)}\n")
