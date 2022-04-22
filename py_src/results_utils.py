import logging
import asyncio
import json
import shutil
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Optional, Union, Dict, List

from GUI_utils import Node, bounds_included
from adb_utils import get_current_activity_name
from consts import BLIND_MONKEY_TAG, BLIND_MONKEY_EVENTS_TAG
from latte_executor_utils import ExecutionResult, latte_capture_layout as capture_layout
from padb_utils import ParallelADBLogger, save_screenshot
from utils import annotate_rectangle


logger = logging.getLogger(__name__)


class OAC(Enum):  # Overly Accessible Condition
    P1_OUT_OF_BOUNDS = 1
    P2_COVERED = 2
    P3_ZERO_AREA = 3
    P4_AINVISIBLE = 4
    P5_BELONGS = 5
    P6_INVALID_BOUNDS = 6
    A1_PINVISIBLE = 101
    A2_CONDITIONAL_DISABLED = 102
    A3_CAMOUFLAGED = 104
    O_AD = -1
    O_P12 = -2
    O_P13 = -3
    O_P14 = -4
    O_P15 = -5
    O_P23 = -6
    O_P24 = -7
    O_P25 = -8
    O_P34 = -9
    O_P35 = -10
    O_P45 = -11
    O_P16 = -12
    O_P26 = -13
    O_P36 = -14
    O_P46 = -15
    O_P56 = -16



class AddressBook:
    def __init__(self, snapshot_result_path: Union[Path, str]):
        if isinstance(snapshot_result_path, str):
            snapshot_result_path = Path(snapshot_result_path)
        self.snapshot_result_path = snapshot_result_path
        navigate_modes = ["tb", "reg", "areg", "exp", "s_reg", "s_areg", "s_tb", "s_exp"]
        self.mode_path_map = {}
        for mode in navigate_modes:
            self.mode_path_map[mode] = self.snapshot_result_path.joinpath(mode.upper())
        self.ovsersight_path = self.snapshot_result_path.joinpath("OS")
        self.oversight_tag = self.ovsersight_path.joinpath("tags.jsonl")
        self.atf_issues_path = self.mode_path_map['exp'].joinpath("atf_issues.jsonl")
        self.action_path = self.snapshot_result_path.joinpath("action.jsonl")
        self.all_element_screenshot = self.mode_path_map['exp'].joinpath("all_elements.png")
        self.atf_issues_screenshot = self.mode_path_map['exp'].joinpath("atf_elements.png")
        self.all_action_screenshot = self.mode_path_map['exp'].joinpath("all_actions.png")
        self.valid_action_screenshot = self.mode_path_map['exp'].joinpath("valid_actions.png")
        self.redundant_action_screenshot = self.mode_path_map['exp'].joinpath("redundant_actions.png")
        self.visited_action_screenshot = self.mode_path_map['exp'].joinpath("visited_actions.png")
        self.visited_elements_screenshot = self.mode_path_map['exp'].joinpath("visited_elements.png")
        self.finished_path = self.snapshot_result_path.joinpath("finished.flag")
        self.last_explore_log_path = self.snapshot_result_path.joinpath("last_explore.log")
        self.visited_elements_path = self.snapshot_result_path.joinpath("visited.jsonl")
        self.valid_elements_path = self.snapshot_result_path.joinpath("valid_elements.jsonl")
        self.tags_path = self.snapshot_result_path.joinpath("tags.jsonl")
        self.s_possible_action_path = self.snapshot_result_path.joinpath("s_possible_action.jsonl")
        self.s_action_path = self.snapshot_result_path.joinpath("s_action.jsonl")
        self.s_action_screenshot = self.mode_path_map['s_exp'].joinpath("all_actions.png")

    def initiate(self):
        if self.snapshot_result_path.exists():
            shutil.rmtree(self.snapshot_result_path.absolute())
        self.snapshot_result_path.mkdir()
        self.ovsersight_path.mkdir()
        for path in self.mode_path_map.values():
            path.mkdir()
        self.action_path.touch()
        self.visited_elements_path.touch()
        self.s_action_path.touch()

    def result_path(self) -> str:
        return self.snapshot_result_path.parent.parent.name

    def get_bm_log_path(self) -> Path:
        return self.snapshot_result_path.parent.joinpath(self.snapshot_result_path.name + ".log")

    def app_name(self) -> str:
        return self.snapshot_result_path.parent.name

    def snapshot_name(self) -> str:
        return self.snapshot_result_path.name

    def get_screenshot_path(self, mode: str, index: Union[int, str], extension: str = None, should_exists: bool = False):
        file_name = f"{index}_{extension}.png" if extension else f"{index}.png"
        if not extension and mode == 's_exp':
            file_name = "INITIAL.png"
        return self._get_path(mode, file_name, should_exists)

    def get_layout_path(self, mode: str, index: int, should_exists: bool = False):
        if mode == 's_exp':
            index = 'INITIAL'
        return self._get_path(mode, f"{index}.xml", should_exists)

    def get_log_path(self, mode: str, index: int, extension: str = None, should_exists: bool = False):
        file_name = f"{index}_{extension}.log" if (extension is not None and extension != BLIND_MONKEY_TAG) else f"{index}.log"
        return self._get_path(mode, file_name, should_exists)

    def get_instrumented_log_path(self, mode: str, index: int, should_exists: bool = False):
        file_name = f"{index}_instrumented.log"
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

    # BlindSimmer
    def get_os_result_path(self, oac: Union[OAC, str] = None, extension: str = "jsonl") -> Path:
        if oac is None:
            oac = "oacs"
        elif isinstance(oac, OAC):
            oac = oac.name
        return self.ovsersight_path.joinpath(f"{oac}.{extension}")

    def get_oacs(self, oac: Union[OAC, str] = None) -> List[Node]:
        path = self.get_os_result_path(oac)
        if not path.exists():
            return []
        oacs = []
        if oac is None:
            oac = "oacs"
        elif isinstance(oac, OAC):
            oac = oac.name
        with open(path) as f:
            for line in f.readlines():
                res = json.loads(line)
                if oac == "oacs":
                    node = Node.createNodeFromDict(res['node'])
                else:
                    node = Node.createNodeFromDict(res)
                oacs.append(node)
        return oacs

    def get_oacs_with_info(self, oac: Union[OAC, str] = None) -> Dict[Node, Dict]:
        oac_nodes = self.get_oacs(oac)
        oac_info_map = {}
        tb_reachable_xpaths = {}
        if self.visited_elements_path.exists():
            with open(self.visited_elements_path) as f:
                for res in f.readlines():
                    element = json.loads(res)['element']
                    node = Node.createNodeFromDict(element)
                    if node.area() >= 0.8 * (1080*2340): # TODO: CONSTANT...
                        continue
                    tb_reachable_xpaths[element['xpath']] = element
        tb_actions_xpaths = {}
        if self.action_path.exists():
            with open(self.action_path) as f:
                for action in f.readlines():
                    action = json.loads(action)
                    with open(self.get_log_path('tb', action['index'], extension=BLIND_MONKEY_EVENTS_TAG)) as f2:
                        if "TYPE_VIEW_CLICKED" in f2.read():
                            tb_actions_xpaths[action['element']['xpath']] = action
        api_actions_xpaths = {}
        if self.s_action_path.exists():
            with open(self.s_action_path) as f:
                for action in f.readlines():
                    action = json.loads(action)
                    if action['tb_action_result'] is not None:
                        with open(self.get_log_path('s_tb', action['index'], extension=BLIND_MONKEY_EVENTS_TAG)) as f2:
                            if "TYPE_VIEW_CLICKED" in f2.read():
                                tb_actions_xpaths[action['element']['xpath']] = action
                    with open(self.get_log_path('s_areg', action['index'], extension=BLIND_MONKEY_EVENTS_TAG)) as f2:
                        if "TYPE_VIEW_CLICKED" in f2.read():
                            api_actions_xpaths[action['element']['xpath']] = action
        oae_tags = defaultdict(list)
        if self.oversight_tag.exists():
            with open(self.oversight_tag) as f:
                for line in f.readlines():
                    obj = json.loads(line)
                    if obj['oac'] == oac or oac == 'oacs':
                        oae_tags[obj['xpath']].append(obj['tag'])
        for oac_node in oac_nodes:
            info = {}
            max_subseq_tb_element = None
            for tb_xpath in tb_reachable_xpaths:
                if oac_node.xpath.startswith(tb_xpath):
                    tb_node = Node.createNodeFromDict(tb_reachable_xpaths[tb_xpath])
                    # if not bounds_included(tb_node.bounds, oac_node.bounds):
                    #     continue
                    if max_subseq_tb_element is None or len(max_subseq_tb_element['xpath']) < len(tb_xpath):
                        max_subseq_tb_element = tb_reachable_xpaths[tb_xpath]
            info['tbr'] = max_subseq_tb_element
            min_subseq_tb_action = None
            if info['tbr'] is not None:
                for tb_xpath in tb_actions_xpaths:
                    if tb_xpath.startswith(oac_node.xpath):
                        tb_node = Node.createNodeFromDict(tb_actions_xpaths[tb_xpath])
                        # if not bounds_included(oac_node.bounds, tb_node.bounds):
                        #     continue
                        if min_subseq_tb_action is None or len(min_subseq_tb_action['element']['xpath']) < len(tb_xpath):
                            min_subseq_tb_action = tb_actions_xpaths[tb_xpath]
            info['tba'] = min_subseq_tb_action
            min_subseq_api_action = None
            for api_xpath in api_actions_xpaths:
                if api_xpath.startswith(oac_node.xpath):
                    api_node = Node.createNodeFromDict(api_actions_xpaths[api_xpath])
                    # if not bounds_included(oac_node.bounds, api_node.bounds):
                    #     continue
                    if min_subseq_api_action is None or len(min_subseq_api_action['element']['xpath']) < len(api_xpath):
                        min_subseq_api_action = api_actions_xpaths[api_xpath]
            info['apia'] = min_subseq_api_action
            info['tags'] = oae_tags[oac_node.xpath]
            oac_info_map[oac_node] = info
        return oac_info_map


class ResultWriter:
    def __init__(self, address_book: AddressBook):
        self.address_book = address_book
        self.visited_elements = []
        self.actions = []

    def visit_element(self, visited_element: dict, state: str, node: Union[Node, None]) -> None:
        """
        Write the visited element into exploration result
        :param visited_element: The element that is visited by Latte
        :param state: The state of the visited element can be 'skipped', 'repetitive', 'selected'
        :param node: The equivalent element with more information such as 'clickable' or 'focused'
        """
        use_detailed = node is not None
        # TODO: Fix this
        # if use_detailed:
        #     for key in visited_element:
        #         if key not in node or key == 'bounds':
        #             continue
        #         if visited_element[key] != node[key]:
        #             use_detailed = False
        #             logger.warning(f"The detailed element doesn't match. Visited Element: {visited_element},"
        #                          f" Node: {node}")
        #             break
        visited_element = {
            'index': len(self.visited_elements),
            'state': state,
            'element': visited_element,
            'node': json.loads(node.toJSONStr()) if use_detailed else None
        }
        self.visited_elements.append(visited_element)
        with open(self.address_book.visited_elements_path, "a") as f:
            f.write(f"{json.dumps(visited_element)}\n")

    def get_action_index(self):
        return len(self.actions)

    def add_action(self,
                   element: dict,
                   tb_action_result: Union[str, ExecutionResult],
                   reg_action_result: ExecutionResult,
                   areg_action_result: ExecutionResult = None,
                   node: Node = None,
                   is_sighted: bool = False):
        action_index = self.get_action_index()
        if not is_sighted:
            exp_screenshot_path = self.address_book.get_screenshot_path('exp', action_index, should_exists=True)
            if exp_screenshot_path:
                annotate_rectangle(exp_screenshot_path,
                                   self.address_book.get_screenshot_path('exp', action_index, extension="edited"),
                                   [reg_action_result.bound],
                                   outline=(0, 255, 255),
                                   scale=15,
                                   width=15,)
        else:
            initial_path = self.address_book.get_screenshot_path('s_exp', 'INITIAL', should_exists=True)
            if initial_path is not None:
                if isinstance(tb_action_result, ExecutionResult):
                    annotate_rectangle(initial_path,
                                       self.address_book.get_screenshot_path('s_exp', action_index, extension="edited"),
                                       bounds=[reg_action_result.bound, tb_action_result.bound],
                                       outline=[(255, 0, 255), (255, 255, 0)],
                                       width=[5, 15],
                                       scale=[1, 20])
                else:
                    annotate_rectangle(initial_path,
                                       self.address_book.get_screenshot_path('s_exp', action_index, extension="edited"),
                                       bounds=[reg_action_result.bound],
                                       outline=(255, 0, 255),
                                       width=5,
                                       scale=1)
        new_action = {'index': action_index,
                      'element': element,
                      'tb_action_result': tb_action_result,
                      'reg_action_result': reg_action_result,
                      'areg_action_result': areg_action_result,
                      'node': None if node is None else json.loads(node.toJSONStr()),
                      'is_sighted': is_sighted
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

    async def capture_current_state(self, device,
                                    mode: str,
                                    index: Union[int, str],
                                    has_layout=True,
                                    log_message_map: Optional[dict] = None) -> str:
        await asyncio.sleep(3)
        await save_screenshot(device, self.address_book.get_screenshot_path(mode, index))
        activity_name = await get_current_activity_name()
        with open(self.address_book.get_activity_name_path(mode, index), mode='w') as f:
            f.write(activity_name + "\n")

        layout = ""
        if has_layout:
            padb_logger = ParallelADBLogger(device)
            log_map, layout = await padb_logger.execute_async_with_log(capture_layout())
            with open(self.address_book.get_log_path(mode, index, extension="layout"), mode='w') as f:
                f.write(log_map[BLIND_MONKEY_TAG])
            with open(self.address_book.get_layout_path(mode, index), mode='w') as f:
                f.write(layout)

        if log_message_map:
            for tag, log_message in log_message_map.items():
                with open(self.address_book.get_log_path(mode, index, extension=tag), mode='w') as f:
                    f.write(log_message)

        return layout  # TODO: Remove it

    def write_last_navigate_log(self, log_message: str):
        with open(self.address_book.last_explore_log_path, mode='w') as f:
            f.write(log_message)


def get_snapshot_paths(result_path: Union[str, Path] = None,
                       app_path: Union[str, Path] = None,
                       snapshot_path: Union[str, Path] = None) -> List[Path]:
    available_paths = 0
    if snapshot_path:
        available_paths += 1
    if app_path:
        available_paths += 1
    if result_path:
        available_paths += 1

    if available_paths != 1:
        logger.error(f"Error. You must provide exactly one path to process!")
        return []

    snapshot_paths = []

    if result_path:
        result_path = Path(result_path) if isinstance(result_path, str) else result_path
        if not result_path.is_dir():
            logger.error(f"The result path doesn't exist! {result_path}")
            return []
        for app_path in result_path.iterdir():
            if not app_path.is_dir():
                continue
            for snapshot_path in app_path.iterdir():
                if not snapshot_path.is_dir():
                    continue
                snapshot_paths.append(snapshot_path)
    elif app_path:
        app_path = Path(app_path) if isinstance(app_path, str) else app_path
        if not app_path.is_dir():
            logger.error(f"The app path doesn't exist! {app_path}")
            return []
        for snapshot_path in app_path.iterdir():
            if not snapshot_path.is_dir():
                continue
            snapshot_paths.append(snapshot_path)
    elif snapshot_path:
        snapshot_path = Path(snapshot_path) if isinstance(snapshot_path, str) else snapshot_path
        if not snapshot_path.is_dir():
            logger.error(f"The snapshot doesn't exist! {snapshot_path}")
            return []
        snapshot_paths.append(snapshot_path)

    return snapshot_paths


def read_all_visited_elements_in_app(app_path: Union[str, Path]) -> Dict[str, Node]:
    """
    Given the result path of an app, returns visited nodes, mapping xpath to the list of its nodes
    """
    visited_elements = {}
    app_path = Path(app_path) if isinstance(app_path, str) else app_path
    for snapshot_path in app_path.iterdir():
        if not snapshot_path.is_dir():
            continue
        address_book = AddressBook(snapshot_path)
        if not address_book.visited_elements_path.exists():
            continue
        if not address_book.finished_path.exists():
            continue
        with open(address_book.visited_elements_path) as f:
            for line in f.readlines():
                element = json.loads(line)
                if element['state'] != 'selected' or element['node'] is None:
                    continue
                visited_elements.setdefault(element['element']['xpath'], [])
                visited_elements[element['element']['xpath']].append(Node.createNodeFromDict(element['node']))
        with open(address_book.s_action_path) as f:
            for line in f.readlines():
                action = json.loads(line)
                visited_elements.setdefault(action['element']['xpath'], [])
                visited_elements[action['element']['xpath']].append(Node.createNodeFromDict(action['node']))
    return visited_elements
