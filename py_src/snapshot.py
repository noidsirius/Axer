import asyncio
import logging
import shutil
from pathlib import Path
from typing import Union, Callable, List
from ppadb.client_async import ClientAsync as AdbClient
from ppadb.device_async import DeviceAsync

from GUI_utils import NodesFactory, Node, is_in_same_state_with_nodes
from a11y_service import A11yServiceManager
from adb_utils import save_snapshot, load_snapshot
from consts import DEVICE_NAME, ADB_HOST, ADB_PORT
from results_utils import AddressBook, capture_current_state
from utils import synch_run

logger = logging.getLogger(__name__)


class Snapshot:
    def __init__(self, address_book: AddressBook):
        address_book.initiate()
        self.address_book = address_book
        self.name = address_book.snapshot_name()
        self.initial_layout = None
        self.initial_screenshot = None
        self.nodes = []
        self.xpath_to_node = {}
        self._setup_completed = False

    async def setup(self,
                    layout: str = None,
                    layout_path: Union[str, Path] = None,
                    screenshot: Union[str, Path] = None,
                    **kwargs):
        if self._setup_completed:
            return
        if layout is None and layout_path is None:
            layout_path = self.address_book.get_layout_path(mode=AddressBook.BASE_MODE,
                                                            index=AddressBook.INITIAL,
                                                            should_exists=True)
            screenshot = self.address_book.get_screenshot_path(mode=AddressBook.BASE_MODE,
                                                               index=AddressBook.INITIAL,
                                                               should_exists=True)
            if layout_path is None:
                raise Exception(f"The layout is not provided for snapshot {self.name}!")
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

        for node in self.nodes:
            self.xpath_to_node[node.xpath] = node

        # TODO: should not be here
        if not self.address_book.snapshot_result_path.joinpath("nodes.jsonl").exists():
            with open(self.address_book.snapshot_result_path.joinpath("nodes.jsonl"), "w") as f:
                for node in self.nodes:
                    f.write(f"{node.toJSONStr()}\n")

        self._setup_completed = True

    def clone(self, target_address_book: AddressBook) -> 'Snapshot':
        shutil.copytree(self.address_book.snapshot_result_path, target_address_book.snapshot_result_path, )
        return Snapshot(target_address_book)

    def get_nodes(self, filter_query: Callable[[Node], bool] = None):
        if filter_query is None:
            filter_query = lambda x: True

        return [node for node in self.nodes if filter_query(node)]

    def get_text_description(self, node: Node) -> List[str]:
        def max_subsequenc_substring(string_1, string_2, n, m) -> int:
            # Copied from https://www.geeksforgeeks.org/find-length-longest-subsequence-one-string-substring-another-string/
            MAX_LENGTH = 1000
            dp = [[0 for i in range(MAX_LENGTH)]
                  for i in range(MAX_LENGTH)]

            # Initialize the dp[][] to 0.

            # Calculating value for each element.
            for i in range(1, m + 1):
                for j in range(1, n + 1):

                    # If alphabet of string
                    # X and Y are equal make
                    # dp[i][j] = 1 + dp[i-1][j-1]
                    if(string_1[j - 1] == string_2[i - 1]):
                        dp[i][j] = 1 + dp[i - 1][j - 1]

                    # Else copy the previous value
                    # in the row i.e dp[i-1][j-1]
                    else:
                        dp[i][j] = dp[i][j - 1]

            # Finding the maximum length
            ans = 0
            for i in range(1, m + 1):
                ans = max(ans, dp[i][n])
            return ans
        my_node: Node = None
        if node.xml_element is not None:
            my_node = node
        else:
            for t_node in self.nodes:
                if t_node.xpath == node.xpath:
                    my_node = t_node
                    break
            if my_node is None:
                similar_nodes = []
                for t_node in self.nodes:
                    if t_node.almost_same_xpath(node):
                        sim = max_subsequenc_substring(node.xpath, t_node.xpath, len(node.xpath), len(t_node.xpath))
                        similar_nodes.append((t_node, sim))
                if len(similar_nodes) > 0:
                    my_node = max(similar_nodes, key=lambda x: x[1])[0]
        if my_node is None:
            return []
        if my_node.content_desc:
            return [my_node.content_desc]
        if my_node.text:
            return [my_node.text]
        text_description = []
        for child in my_node.children_nodes:
            text_description.extend(self.get_text_description(child))
        text_description = [x.strip() for x in text_description if len(x.strip()) > 0]
        return text_description


    def is_in_same_state_as(self, other_snapshot: 'Snapshot') -> bool:
        logger.debug(f"Comparing with {other_snapshot.address_book.snapshot_name()}")
        if self.address_book.package_name() != other_snapshot.address_book.package_name():
            return False
        if not self.initial_layout or not other_snapshot.initial_layout or not self.nodes or not other_snapshot.nodes:
            logger.error(f"The layout is missing: "
                         f"First Path: {self.address_book.snapshot_result_path}, "
                         f"Second Path: {other_snapshot.address_book.snapshot_result_path}")
            return False
        return is_in_same_state_with_nodes(self.nodes, other_snapshot.nodes,
                                           extra_excluded_attributes=['checked', 'selected', 'text', 'content_desc',
                                                                      'visible'],
                                           package_name=self.address_book.package_name())


class DeviceSnapshot(Snapshot):
    def __init__(self, address_book: AddressBook, device: DeviceAsync = None):
        super().__init__(address_book=address_book)
        if device is None:
            client = AdbClient(host=ADB_HOST, port=ADB_PORT)
            device = synch_run(client.device(DEVICE_NAME))
        self.device = device

    async def setup(self, first_setup: bool = True, dumpsys: bool = True, use_service: bool = True,
                    enabled_assistive_services: List[str] = None, **kwargs):
        initial_layout = initial_screenshot = None
        if first_setup:
            if use_service:
                has_tb = enabled_assistive_services is not None and "tb" in enabled_assistive_services
                await A11yServiceManager.setup_latte_a11y_services(tb=has_tb, device_name=self.device.serial)
            initial_layout = await capture_current_state(self.address_book,
                                                         self.device,
                                                         mode=AddressBook.BASE_MODE,
                                                         index=AddressBook.INITIAL,
                                                         dumpsys=dumpsys,
                                                         has_layout=True,
                                                         use_adb_layout=not use_service)
            initial_screenshot = self.address_book.get_screenshot_path(AddressBook.BASE_MODE, AddressBook.INITIAL)
        await super().setup(layout=initial_layout, screenshot=initial_screenshot, **kwargs)


class EmulatorSnapshot(DeviceSnapshot):
    def __init__(self, address_book: AddressBook, device: DeviceAsync = None, no_save_snapshot: bool = False):
        super().__init__(address_book=address_book, device=device)
        self.tmp_snapshot = self.address_book.snapshot_name() + "_TMP"
        self.no_save_snapshot = no_save_snapshot

    async def setup(self, first_setup: bool = True, initial_emulator_load: bool = False, **kwargs):
        if initial_emulator_load:
            if not await load_snapshot(self.address_book.snapshot_name(), device_name=self.device.serial):
                raise Exception("Error in loading snapshot")

        await super().setup(first_setup=first_setup, **kwargs)
        if first_setup and not self.no_save_snapshot:
            await asyncio.sleep(3)
            await save_snapshot(self.tmp_snapshot, device_name=self.device.serial)

    async def reload(self, hard: bool = False) -> bool:
        if hard:
            if not await load_snapshot(self.address_book.snapshot_name(), device_name=self.device.serial):
                return False
            await asyncio.sleep(3)
            if not self.no_save_snapshot:
                await save_snapshot(self.tmp_snapshot, device_name=self.device.serial)
            return True
        if self.no_save_snapshot:
            logger.error("There is no temporary snapshot saved!")
            return False
        result = await load_snapshot(self.tmp_snapshot, device_name=self.device.serial)
        await asyncio.sleep(3)
        return result
