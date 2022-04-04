import asyncio
import logging
from pathlib import Path
from typing import Union, Callable
from ppadb.client_async import ClientAsync as AdbClient
from ppadb.device_async import DeviceAsync

from GUI_utils import NodesFactory, Node
from a11y_service import A11yServiceManager
from adb_utils import save_snapshot, load_snapshot
from consts import DEVICE_NAME, ADB_HOST, ADB_PORT
from controller import TalkBackDirectionalController
from results_utils import AddressBook, capture_current_state

logger = logging.getLogger(__name__)


class Snapshot:
    def __init__(self, address_book: AddressBook):
        address_book.initiate()
        self.address_book = address_book
        self.initial_layout = None
        self.initial_screenshot = None
        self.nodes = []

    async def setup(self,
                    layout: str = None,
                    layout_path: Union[str, Path] = None,
                    screenshot: Union[str, Path] = None,
                    **kwargs):
        if layout is None and layout_path is None:
            layout_path = self.address_book.get_layout_path(mode=AddressBook.BASE_MODE,
                                                            index=AddressBook.INITIAL,
                                                            should_exists=True)
            screenshot = self.address_book.get_screenshot_path(mode=AddressBook.BASE_MODE,
                                                               index=AddressBook.INITIAL,
                                                               should_exists=True)
            if layout_path is None:
                raise Exception("The layout is not provided!")
        if layout_path is not None:
            with open(layout_path) as f:
                layout = f.read()
        self.initial_layout = layout
        self.initial_screenshot = screenshot
        self.nodes = NodesFactory() \
            .with_layout(self.initial_layout) \
            .with_xpath_pass() \
            .with_ad_detection() \
            .build()

    def get_nodes(self, filter_query: Callable[[Node], bool] = None):
        if filter_query is None:
            filter_query = lambda x: True

        return [node for node in self.nodes if filter_query(node)]


class DeviceSnapshot(Snapshot):
    def __init__(self, address_book: AddressBook, device: DeviceAsync = None):
        super().__init__(address_book=address_book)
        if device is None:
            client = AdbClient(host=ADB_HOST, port=ADB_PORT)
            device = asyncio.run(client.device(DEVICE_NAME))
        self.device = device

    async def setup(self, first_setup: bool = True, **kwargs):
        initial_layout = initial_screenshot = None
        if first_setup:
            await A11yServiceManager.setup_latte_a11y_services(tb=True)
            initial_layout = await capture_current_state(self.address_book,
                                                         self.device,
                                                         mode=AddressBook.BASE_MODE,
                                                         index=AddressBook.INITIAL,
                                                         has_layout=True)
            initial_screenshot = self.address_book.get_screenshot_path(AddressBook.BASE_MODE, AddressBook.INITIAL)
        await super().setup(layout=initial_layout, screenshot=initial_screenshot, **kwargs)


class EmulatorSnapshot(DeviceSnapshot):
    def __init__(self, address_book: AddressBook, device: DeviceAsync = None):
        super().__init__(address_book=address_book, device=device)
        self.tmp_snapshot = self.address_book.snapshot_name() + "_TMP"

    async def setup(self, first_setup: bool = True, initial_emulator_load: bool = False, **kwargs):
        if initial_emulator_load:
            if not await load_snapshot(self.address_book.snapshot_name(), device_name=self.device.serial):
                raise Exception("Error in loading snapshot")

        await super().setup(first_setup=first_setup, **kwargs)
        if first_setup:
            await asyncio.sleep(3)
            await save_snapshot(self.tmp_snapshot)

    async def reload(self, hard: bool = False) -> bool:
        if hard:
            if not await load_snapshot(self.address_book.snapshot_name(), device_name=self.device.serial):
                return False
            await asyncio.sleep(3)
            await save_snapshot(self.tmp_snapshot)
            return True
        result = await load_snapshot(self.tmp_snapshot, device_name=self.device.serial)
        await asyncio.sleep(1)
        return result
