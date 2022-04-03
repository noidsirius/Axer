import asyncio
import logging
from pathlib import Path
from typing import Union
from ppadb.client_async import ClientAsync as AdbClient
from ppadb.device_async import DeviceAsync

from a11y_service import A11yServiceManager
from adb_utils import save_snapshot
from consts import DEVICE_NAME, ADB_HOST, ADB_PORT
from results_utils import AddressBook, capture_current_state

logger = logging.getLogger(__name__)


class Snapshot:
    def __init__(self, address_book: AddressBook, layout: str = None, layout_path: Union[str, Path] = None,
                 screenshot: Union[str, Path] = None):
        if layout is None and layout_path is None:
            layout_path = address_book.get_layout_path(mode=AddressBook.BASE_MODE,
                                                       index=AddressBook.INITIAL,
                                                       should_exists=True)
            screenshot = address_book.get_screenshot_path(mode=AddressBook.BASE_MODE,
                                                          index=AddressBook.INITIAL,
                                                          should_exists=True)
            if layout_path is None:
                raise Exception("The layout is not provided!")
        if layout_path is not None:
            with open(layout_path) as f:
                layout = f.read()
        address_book.initiate()
        self.address_book = address_book
        self.initial_layout = layout
        self.initial_screenshot = screenshot


class DeviceSnapshot(Snapshot):
    def __init__(self, address_book: AddressBook, device: DeviceAsync):
        if device is None:
            client = AdbClient(host=ADB_HOST, port=ADB_PORT)
            device = asyncio.run(client.device(DEVICE_NAME))
        address_book.initiate()
        self.device = device
        asyncio.run(A11yServiceManager.setup_latte_a11y_services(tb=True))
        initial_layout = asyncio.run(capture_current_state(address_book,
                                                           self.device,
                                                           mode=AddressBook.BASE_MODE,
                                                           index="INITIAL",
                                                           has_layout=True))
        initial_screenshot = address_book.get_screenshot_path(AddressBook.BASE_MODE, "INITIAL")
        super().__init__(address_book=address_book, layout=initial_layout, screenshot=initial_screenshot)


class EmulatorSnapshot(DeviceSnapshot):
    def __init__(self, address_book: AddressBook, device: DeviceAsync):
        super().__init__(address_book=address_book, device=device)
        self.tmp_snapshot = self.address_book.snapshot_name() + "_TMP"
        asyncio.run(save_snapshot(self.tmp_snapshot))
