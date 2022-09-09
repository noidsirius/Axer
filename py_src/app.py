import logging
import shutil
from pathlib import Path
from typing import Union, Generator, List

from ppadb.device_async import DeviceAsync

from results_utils import AddressBook
from snapshot import Snapshot, DeviceSnapshot
from utils import synch_run

logger = logging.getLogger(__name__)


class App:
    def __init__(self, app_name: str, result_path: Union[str, Path], recreate: bool = False):
        """

        :param app_name: It should be in format of <PACKAGE_NAME>(<ID>) where <PACKAGE_NAME> is the package name of the
        app and <ID> is optional, e.g., 'com.apple.movetoios(E2)', 'com.apple.movetoios', and `com.dictionary(Login)`
        :param result_path: The directory storing the app information
        """
        if isinstance(result_path, str):
            result_path = Path(result_path)
        self.package_name = app_name.split('(')[0]
        self.id = app_name.split('(')[1][:-1] if '(' in app_name else ''
        self.app_path = result_path.joinpath(app_name)
        if recreate and self.app_path.exists():
            shutil.rmtree(self.app_path)
        self.app_path.mkdir(parents=True, exist_ok=True)
        if not self.app_path.exists():
            raise f"The app path {self.app_path} does not exist!"
        self.snapshot_map = {}
        self.update_snapshots()

    def update_snapshots(self):
        self.snapshot_map = {}
        for snapshot_result_path in self.app_path.iterdir():
            if snapshot_result_path.is_dir():
                snapshot_name = snapshot_result_path.name
                if snapshot_name.startswith('REPLAY_'):  # TODO: A better solution
                    continue
                if snapshot_name == 'SERVER':  # TODO: A better solution
                    continue
                if snapshot_name == 'RECORDER':  # TODO: A better solution
                    continue
                if snapshot_name.startswith('TMP'):  # TODO: A better solution
                    continue
                address_book = AddressBook(snapshot_result_path=snapshot_result_path)
                self.snapshot_map[snapshot_name] = Snapshot(address_book)

    def get_snapshot(self, name: str) -> Union[Snapshot, None]:
        if name not in self.snapshot_map:
            return None
        synch_run(self.snapshot_map[name].setup())
        return self.snapshot_map[name]

    async def async_get_snapshot(self, name: str) -> Union[Snapshot, None]:
        if name not in self.snapshot_map:
            return None
        await self.snapshot_map[name].setup()
        return self.snapshot_map[name]

    @property
    def app_name(self) -> str:
        if self.id:
            return f"{self.package_name}({self.id})"
        return self.package_name

    @property
    def snapshots(self) -> Generator[Snapshot, None, None]:
        for snapshot_name in self.snapshot_map:
            yield self.get_snapshot(snapshot_name)

    async def async_get_snapshots(self) -> Generator[Snapshot, None, None]:
        for snapshot_name in self.snapshot_map:
            yield await self.async_get_snapshot(snapshot_name)

    async def take_snapshot(self, device: DeviceAsync, snapshot_name: str = None,
                            enabled_assistive_services: List[str] = None) -> Snapshot:
        if snapshot_name is None:
            last_index = 0
            for snapshot_name in self.snapshot_map.keys():
                if snapshot_name.startswith("S_"):
                    s_index = snapshot_name[len("S_"):]
                    if s_index.isdigit():
                        last_index = max(last_index, int(s_index))
            snapshot_name = f"S_{last_index+1}"
        if snapshot_name in self.snapshot_map:
            logger.error(f"The snapshot already exists! Return the existing snapshot instead of taking a new snapshot")
            return await self.async_get_snapshot(snapshot_name)
        address_book = AddressBook(self.app_path.joinpath(snapshot_name))
        snapshot = DeviceSnapshot(address_book=address_book, device=device)
        await snapshot.setup(first_setup=True, enabled_assistive_services=enabled_assistive_services)
        self.snapshot_map[snapshot_name] = snapshot
        return snapshot
