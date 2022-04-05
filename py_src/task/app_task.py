from pathlib import Path
from typing import Union

from ppadb.device_async import DeviceAsync

from results_utils import AddressBook
from snapshot import DeviceSnapshot


class AppTask:
    def __init__(self, app_path: Union[Path, str], device: DeviceAsync):
        if isinstance(app_path, str):
            app_path = Path(app_path)
        if not app_path.exists() or not app_path.is_dir():
            raise Exception("The app path doesn't exists")
        self.app_path = app_path
        self.device = device

    def app_name(self):
        return self.app_path.name.split('(')[0]

    async def execute(self):
        pass


class TakeSnapshotTask(AppTask):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def execute(self):
        last_index = 0
        for subdir in self.app_path.iterdir():
            if subdir.is_dir() and subdir.name.startswith("S_"):
                s_index = subdir.name[len("S_"):]
                if s_index.isdigit():
                    last_index = max(last_index, int(s_index))
        snapshot_name = f"S_{last_index+1}"
        address_book = AddressBook(self.app_path.joinpath(snapshot_name))
        snapshot = DeviceSnapshot(address_book=address_book, device=self.device)
        await snapshot.setup(first_setup=True)
