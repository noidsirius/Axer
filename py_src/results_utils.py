import logging
import asyncio
import json
import shutil
from pathlib import Path
from typing import Optional, Union
from adb_utils import get_current_activity_name
from latte_utils import latte_capture_layout as capture_layout
from latte_utils import ExecutionResult
from padb_utils import ParallelADBLogger, save_screenshot
from utils import annotate_rectangle


logger = logging.getLogger(__name__)


class AddressBook:
    def __init__(self, snapshot_result_path: Union[Path, str]):
        if isinstance(snapshot_result_path, str):
            snapshot_result_path = Path(snapshot_result_path)
        self.snapshot_result_path = snapshot_result_path
        navigate_modes = ["tb", "reg", "exp", "s_reg", "s_tb", "s_exp"]
        self.mode_path_map = {}
        for mode in navigate_modes:
            self.mode_path_map[mode] = self.snapshot_result_path.joinpath(mode.upper())
        self.action_path = self.snapshot_result_path.joinpath("action.jsonl")
        self.visited_elements_path = self.snapshot_result_path.joinpath("visited.jsonl")
        self.s_action_path = self.snapshot_result_path.joinpath("s_action.jsonl")

    def initiate(self):
        if self.snapshot_result_path.exists():
            shutil.rmtree(self.snapshot_result_path.absolute())
        self.snapshot_result_path.mkdir()
        for path in self.mode_path_map.values():
            path.mkdir()
        self.action_path.touch()
        self.visited_elements_path.touch()
        self.s_action_path.touch()

    def get_screenshot_path(self, mode: str, index: Union[int, str], extension: str = None, should_exists: bool = False):
        file_name = f"{index}_{extension}.png" if extension else f"{index}.png"
        return self._get_path(mode, file_name, should_exists)

    def get_layout_path(self, mode: str, index: int, should_exists: bool = False):
        return self._get_path(mode, f"{index}.xml", should_exists)

    def get_log_path(self, mode: str, index: int, is_layout: bool = False, should_exists: bool = False):
        file_name = f"{index}_layout.log" if is_layout else f"{index}.log"
        return self._get_path(mode, file_name, should_exists)

    def get_activity_name_path(self, mode: str, index: int, should_exists: bool = False):
        return self._get_path(mode, f"{index}_activity_name.txt", should_exists)

    def _get_path(self, mode: str, file_name_with_extension: str, should_exists: bool):
        if mode not in self.mode_path_map:
            return None
        path = self.mode_path_map[mode].joinpath(file_name_with_extension)
        if should_exists and not path.exists():
            return None
        return path


class ResultWriter:
    def __init__(self, address_book: AddressBook):
        self.address_book = address_book
        self.visited_elements = []
        self.actions = []

    def visit_element(self, element: dict):
        visited_element = {'index': len(self.visited_elements), 'element': element}
        self.visited_elements.append(visited_element)
        with open(self.address_book.visited_elements_path, "a") as f:
            f.write(f"{json.dumps(visited_element)}\n")

    def get_action_index(self):
        return len(self.actions)

    def add_action(self,
                   element: dict,
                   tb_action_result: Union[str, ExecutionResult],
                   reg_action_result: ExecutionResult,
                   is_sighted: bool = False):
        action_index = self.get_action_index()
        if not is_sighted:
            exp_screenshot_path = self.address_book.get_screenshot_path('exp', action_index, should_exists=True)
            if exp_screenshot_path:
                annotate_rectangle(exp_screenshot_path,
                                   self.address_book.get_screenshot_path('exp', action_index, extension="edited"),
                                   reg_action_result.bound,
                                   outline=(0, 255, 255),
                                   scale=15,
                                   width=15,)
        else:
            initial_path = self.address_book.get_screenshot_path('s_exp', 'INITIAL', should_exists=True)
            if initial_path is not None and isinstance(tb_action_result, ExecutionResult):
                annotate_rectangle(initial_path,
                                   self.address_book.get_screenshot_path('s_exp', action_index, extension="R"),
                                   reg_action_result.bound,
                                   outline=(255, 0, 255),
                                   width=5,
                                   scale=1)
                annotate_rectangle(self.address_book.get_screenshot_path('s_exp', action_index, extension="R"),
                                   self.address_book.get_screenshot_path('s_exp', action_index, extension="edited"),
                                   tb_action_result.bound,
                                   outline=(255, 255, 0),
                                   width=15,
                                   scale=20)
        new_action = {'index': action_index,
                      'element': element,
                      'tb_action_result': tb_action_result,
                      'reg_action_result': reg_action_result,
                      }
        self.actions.append(new_action)
        action_path = self.address_book.s_action_path if is_sighted else self.address_book.action_path
        with open(action_path, "a") as f:
            f.write(f"{json.dumps(new_action)}\n")

    def start_explore(self):
        self.address_book.initiate()
        self.visited_elements = []
        self.actions = []

    def start_stb(self):
        self.actions = []

    async def capture_current_state(self, device, mode: str, index: Union[int, str], has_layout=True,
                                    log_message: Optional[str] = None) -> str:
        await asyncio.sleep(3)
        await save_screenshot(device, self.address_book.get_screenshot_path(mode, index))
        activity_name = await get_current_activity_name()
        with open(self.address_book.get_activity_name_path(mode, index), mode='w') as f:
            f.write(activity_name + "\n")

        layout = ""
        if has_layout:
            padb_logger = ParallelADBLogger(device)
            log, layout = await padb_logger.execute_async_with_log(capture_layout())
            with open(self.address_book.get_log_path(mode, index, is_layout=True), mode='w') as f:
                f.write(log)
            with open(self.address_book.get_layout_path(mode, index), mode='w') as f:
                f.write(layout)

        if log_message:
            with open(self.address_book.get_log_path(mode, index), mode='w') as f:
                f.write(log_message)

        return layout  # TODO: Remove it