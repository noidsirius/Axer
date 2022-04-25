import logging

from snapshot import EmulatorSnapshot
from task.snapshot_task import SnapshotTask

logger = logging.getLogger(__name__)


class PerformActionsTask(SnapshotTask):
    def __init__(self, snapshot: EmulatorSnapshot, check_both_directions: bool = False):
        if not isinstance(snapshot, EmulatorSnapshot):
            raise Exception("Perform Actions task requires a EmulatorSnapshot!")
        super().__init__(snapshot)

    async def execute(self):
        pass

