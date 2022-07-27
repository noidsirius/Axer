import json
import logging

from ppadb.device_async import DeviceAsync

from command import LocatableCommandResponse, Command, LocatableCommand, create_command_response_from_dict, \
    CommandResponse, ClickCommand, SelectCommand
from consts import BLIND_MONKEY_TAG, BLIND_MONKEY_EVENTS_TAG
from controller import Controller, TalkBackDirectionalController
from padb_utils import ParallelADBLogger
from results_utils import capture_current_state
from snapshot import Snapshot, DeviceSnapshot
from task.snapshot_task import SnapshotTask
from task.talkback_explore_task import TalkBackExploreTask

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
        result = {
            'controller': self.controller.mode(),
            'command': self.command.toJSON(),
            'response': create_command_response_from_dict(self.command, result={}).toJSON(),
        }
        tags = [BLIND_MONKEY_TAG, BLIND_MONKEY_EVENTS_TAG]
        if isinstance(self.controller, TalkBackDirectionalController) and isinstance(self.command, LocatableCommand):
            device_snapshot = DeviceSnapshot(address_book=self.snapshot.address_book, device=self.device)
            await device_snapshot.setup(first_setup=False)
            is_located = False
            for node in device_snapshot.nodes:
                if self.command.target.same_identifiers(node):
                    is_located = True
                    break
            if is_located:
                is_located = await TalkBackExploreTask(snapshot=device_snapshot, target_node=self.command.target).execute()
            log_message_map: dict = {x: '' for x in tags}
            if is_located:
                logger.info("Target node is focused!")
                if isinstance(self.command, ClickCommand):
                    await self.controller.setup()
                    select_command = SelectCommand()
                    logger.info(f"Executing command {select_command}")
                    select_action_response: CommandResponse = await self.controller.execute(select_command)
                    action_response = LocatableCommandResponse(command_type=self.command.action,
                                                               state=select_action_response.state,
                                                               duration=select_action_response.duration,
                                                               target_node=self.command.target,
                                                               acted_node=select_action_response.navigated_node,
                                                               locating_attempts=0)
            else:
                action_response: CommandResponse = create_command_response_from_dict(self.command, {})
                action_response.state = 'FAILED'
        else:
            padb_logger = ParallelADBLogger(self.device)
            logger.info(f"Setup controller {self.controller.name()}")
            await self.controller.setup()
            logger.info(f"Executing command {self.command}")
            executor_result = await padb_logger.execute_async_with_log(
                self.controller.execute(self.command),
                tags=tags)
            log_message_map: dict = executor_result[0]
            action_response: CommandResponse = executor_result[1]
        logger.info(f"The action is performed in {action_response.duration}ms! State: {action_response.state} ")
        await capture_current_state(self.snapshot.address_book,
                                    self.device,
                                    mode=self.controller.mode(),
                                    index=0,
                                    log_message_map=log_message_map,
                                    dumpsys=True,
                                    has_layout=True)
        result['response'] = action_response.toJSON()
        with open(self.snapshot.address_book.execute_single_action_results_path, "w") as f:
            f.write(f"{json.dumps(result)}\n")
