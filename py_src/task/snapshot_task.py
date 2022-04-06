from snapshot import Snapshot


class SnapshotTask:
    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot

    async def execute(self):
        pass
