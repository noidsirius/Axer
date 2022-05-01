import logging
import asyncio
import json
import shutil
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Optional, Union, Dict, List, Tuple

from GUI_utils import Node, bounds_included, is_in_same_state_with_layout_path, NodesFactory
from adb_utils import get_current_activity_name, get_windows, get_activities, capture_layout as adb_capture_layout
from command import LocatableCommandResponse
from consts import BLIND_MONKEY_TAG, BLIND_MONKEY_EVENTS_TAG
from json_util import JSONSerializable
from latte_executor_utils import ExecutionResult, latte_capture_layout as capture_layout
from padb_utils import ParallelADBLogger, save_screenshot
from utils import annotate_rectangle

logger = logging.getLogger(__name__)


class OAC(Enum):  # Overly Accessible Condition
    P1_BELONGS = 1
    P2_OUT_OF_BOUNDS = 2
    P3_COVERED = 3
    P4_ZERO_AREA = 4
    P5_AINVISIBLE = 5
    A1_PINVISIBLE = 101
    A2_CONDITIONAL_DISABLED = 102
    A3_INCONSISTENT_ABILITIES = 103
    A4_CAMOUFLAGED = 104
    O_AD = -1


class Actionables(Enum):  # Overly Accessible Condition
    All = 1
    UniqueResource = 2
    TBReachable = 3
    TBUnreachable = 4
    NA11y = 5
    Selected = 6
    Spanned = 7


class ActionResult(JSONSerializable):
    def __init__(self, index: int,
                 node: Node,
                 tb_action_result: LocatableCommandResponse,
                 touch_action_result: LocatableCommandResponse,
                 a11y_api_action_result: LocatableCommandResponse,
                 tb_touch_failed: Union[LocatableCommandResponse, None]
                 ):
        self.index = index
        self.node = node
        self.tb_action_result = tb_action_result
        self.touch_action_result = touch_action_result
        self.a11y_api_action_result = a11y_api_action_result
        self.tb_touch_failed = tb_touch_failed

    @staticmethod
    def createFromDict(action_result_json: dict) -> 'ActionResult':
        index = action_result_json.get('index', -1)
        node = Node.createNodeFromDict(action_result_json.get('node', None))
        tb_action_result = LocatableCommandResponse.create_from_response(
            action_result_json.get('tb_action_result', None))
        touch_action_result = LocatableCommandResponse.create_from_response(
            action_result_json.get('touch_action_result', None))
        a11y_api_action_result = LocatableCommandResponse.create_from_response(
            action_result_json.get('a11y_api_action_result', None))
        tb_touch_failed = None if action_result_json.get('tb_touch_failed', None) is None \
            else LocatableCommandResponse.create_from_response(action_result_json['tb_touch_failed'])
        return ActionResult(index=index, node=node, tb_action_result=tb_action_result,
                            touch_action_result=touch_action_result, a11y_api_action_result=a11y_api_action_result,
                            tb_touch_failed=tb_touch_failed)


def extract_events(event_log_message: str) -> List[Tuple[str, Node]]:
    events = []
    for line in event_log_message.split("\n"):
        if "Event: TYPE_" in line:
            try:
                right_part = line[line.find("TYPE_"):]
                event_name = right_part[:right_part.find(" ")]

                node = json.loads(right_part[right_part.find(" "):].strip())
                if node is not None:
                    if 'Element' in node:
                        node = Node.createNodeFromDict(node['Element'])
                    else:
                        logger.warning(f"Problem with analyzing event with node: '{line}'")
                        node = None
                events.append((event_name, node))
            except Exception as e:
                logger.warning(f"Problem in analyzing event: '{e}'")
    return events


def did_talkback_perform_click(events: List[Tuple[str, Node]]) -> bool:
    state = 0
    for event_name, node in reversed(events):
        if event_name == "TYPE_VIEW_CLICKED":
            state = 6
        if state == 0 and event_name == "TYPE_TOUCH_INTERACTION_END":
            state = 1
        elif state == 1:
            if event_name == "TYPE_TOUCH_INTERACTION_START":
                state = 2
            elif event_name in ["TYPE_TOUCH_EXPLORATION_GESTURE_END", "TYPE_TOUCH_EXPLORATION_GESTURE_START"]:
                break
        elif state == 2 and event_name == "TYPE_TOUCH_INTERACTION_END":
            state = 3
        elif state == 3 and event_name == "TYPE_TOUCH_EXPLORATION_GESTURE_END":
            state = 4
        elif state == 4 and event_name == "TYPE_TOUCH_EXPLORATION_GESTURE_START":
            state = 5
        elif state == 5 and event_name == "TYPE_TOUCH_INTERACTION_START":
            state = 6
        elif state == 6:
            break
    return state == 6


def get_clicked_element(events: List[Tuple[str, Node]]) -> Node:
    for event_name, node in reversed(events):
        if event_name == "TYPE_VIEW_CLICKED":
            if node.toJSONStr() == Node().toJSONStr():
                return None
            return node
    return None


class WebHelper:
    def __init__(self, address_book: 'AddressBook'):
        self.address_book = address_book

    def get_action_count(self) -> int:
        if not self.address_book.perform_actions_results_path.exists():
            return 0
        with open(self.address_book.perform_actions_results_path) as f:
            return len(f.readlines())

    def get_atf_count(self) -> int:
        if not self.address_book.perform_actions_atf_issues_path.exists():
            return 0
        with open(self.address_book.perform_actions_atf_issues_path) as f:
            return len(f.readlines())

    def get_action(self, action_index: int) -> ActionResult:
        if not self.address_book.perform_actions_results_path.exists():
            return None
        with open(self.address_book.perform_actions_results_path) as f:
            for line in f.readlines():
                result_json = json.loads(line.strip())
                if result_json['index'] == action_index:
                    return ActionResult.createFromDict(result_json)
        return None

    def get_actions(self) -> List[ActionResult]:
        if not self.address_book.perform_actions_results_path.exists():
            return []
        result = []
        with open(self.address_book.perform_actions_results_path) as f:
            for line in f.readlines():
                result_json = json.loads(line.strip())
                result.append(ActionResult.createFromDict(result_json))
        return result

    def is_same_layout(self, mode1, index1, mode2, index2):
        layout_path1 = self.address_book.get_layout_path(mode1, index1)
        layout_path2 = self.address_book.get_layout_path(mode2, index2)
        return is_in_same_state_with_layout_path(layout_path1, layout_path2)

    def get_events_info(self, mode, index) -> dict:
        event_log_path = self.address_book.get_log_path(mode, index, extension=BLIND_MONKEY_EVENTS_TAG)
        with open(event_log_path) as f:
            event_logs = f.read()
        events = extract_events(event_logs)
        result = {
            'did_tb_click': did_talkback_perform_click(events),
            'clicked_node': get_clicked_element(events)
        }
        return result

    def summarized_events(self, index: int) -> dict:
        mode_result = {}
        modes = ['tb_touch', 'touch', 'a11y_api']
        for mode in modes:
            if index == 2:
                logger.error(f"Here {mode}")
            mode_result[mode] = self.get_events_info(mode, index)
        is_tb_reachable = False
        action_result = self.get_action(index)
        if action_result is None:
            return None
        node = action_result.node
        if self.address_book.extract_actions_nodes[Actionables.TBReachable].exists():
            with open(self.address_book.extract_actions_nodes[Actionables.TBReachable]) as f:
                for line in f.readlines():
                    l_node = Node.createNodeFromDict(json.loads(line))
                    if node is not None and node.xpath and node.xpath == l_node.xpath:
                        is_tb_reachable = True
                        break
        summary = {
            'did_tb_click': mode_result['tb_touch']['did_tb_click'],
            'no_click_at_all': all(mode_result[mode]['clicked_node'] is None for mode in modes),
            'is_tb_reachable': is_tb_reachable,
            'is_tb_touchable': action_result.tb_touch_failed is None,
        }
        same_clicked = True
        for i, mode in enumerate(modes):
            summary[f"{mode}_clicked_node"] = None if mode_result[mode]['clicked_node'] is None else mode_result[mode][
                'clicked_node'].toJSONStr()
            for m2 in modes[i + 1:]:
                same_clicked_in_modes = False
                if mode_result[mode]['clicked_node'] is None:
                    same_clicked_in_modes = mode_result[m2]['clicked_node'] is None
                elif mode_result[m2]['clicked_node'] is None:
                    same_clicked_in_modes = False
                else:
                    same_clicked_in_modes = mode_result[mode]['clicked_node'].xpath == mode_result[m2][
                        'clicked_node'].xpath
                same_clicked = same_clicked and same_clicked_in_modes
                summary[f"same_clicked_{mode}_{m2}"] = same_clicked_in_modes
                summary[f"same_clicked_{m2}_{mode}"] = same_clicked_in_modes
        summary["same_clicked"] = same_clicked
        summary["tb_change_xml"] = not self.is_same_layout(AddressBook.BASE_MODE, index, 'tb_touch', index)
        summary["touch_change_xml"] = not self.is_same_layout(AddressBook.BASE_MODE, index, 'touch', index)
        summary["api_change_xml"] = not self.is_same_layout(AddressBook.BASE_MODE, index, 'a11y_api', index)
        summary["any_change_xml"] = summary["tb_change_xml"] or summary["touch_change_xml"] or summary["api_change_xml"]
        summary["possible_to_locate"] = (summary['is_tb_reachable'] or summary[
            'is_tb_touchable'] or node.important_for_accessibility) and summary["api_change_xml"]
        summary["tb_dir_issue"] = summary["possible_to_locate"] and not summary['is_tb_reachable']
        summary["tb_touch_issue"] = summary["possible_to_locate"] and not summary['is_tb_touchable']
        summary["tb_act_issue"] = summary["any_change_xml"] and not summary["tb_change_xml"] and \
                                  mode_result['tb_touch']['did_tb_click']
        summary["api_act_issue"] = summary["any_change_xml"] and not summary["api_change_xml"]
        summary["touch_act_issue"] = summary["any_change_xml"] and not summary["touch_change_xml"]
        return summary

    def oracle(self) -> dict:
        if not self.address_book.perform_actions_results_path.exists():
            return None
        snapshot_summary = defaultdict(int)
        with open(self.address_book.perform_actions_results_path) as f:
            for line in f.readlines():
                action = json.loads(line.strip())
                index = action['index']
                summary = self.summarized_events(index)
                snapshot_summary["tb_dir_issue"] += 1 if summary["tb_dir_issue"] else 0
                snapshot_summary["tb_touch_issue"] += 1 if summary["tb_touch_issue"] else 0
                snapshot_summary["tb_act_issue"] += 1 if summary["tb_act_issue"] else 0
                snapshot_summary["api_act_issue"] += 1 if summary["api_act_issue"] else 0
                snapshot_summary["touch_act_issue"] += 1 if summary["touch_act_issue"] else 0
        return snapshot_summary

    def get_clickable_span_nodes(self) -> List[Node]:
        nodes = NodesFactory() \
            .with_layout_path(self.address_book.get_layout_path(AddressBook.BASE_MODE, AddressBook.INITIAL)) \
            .with_xpath_pass() \
            .with_ad_detection() \
            .build()
        return [node for node in nodes if node.clickable_span and not node.clickable and node.text]


class AddressBook:
    BASE_MODE = "base"
    INITIAL = "INITIAL"
    ## Audits
    TALKBACK_EXPLORE = "talkback_explore"
    OVERSIGHT_STATIC = "oversight_static"
    PROCESS_SCREENSHOT = "process_screenshot"
    EXTRACT_ACTIONS = "extract_actions"
    PERFORM_ACTIONS = "perform_actions"

    def __init__(self, snapshot_result_path: Union[Path, str]):
        if isinstance(snapshot_result_path, str):
            snapshot_result_path = Path(snapshot_result_path)
        # ---- For Web Visualization ------
        self.whelper = WebHelper(self)
        # --------------

        self.snapshot_result_path = snapshot_result_path
        self.audit_path_map = {}
        # ----------- Audit: talkback_explore ---------------
        self.audit_path_map[AddressBook.TALKBACK_EXPLORE] = self.snapshot_result_path.joinpath("TalkBackExplore")
        self.tb_explore_all_nodes_screenshot = self.audit_path_map[AddressBook.TALKBACK_EXPLORE].joinpath(
            "all_nodes.png")
        self.tb_explore_android_log = self.audit_path_map[AddressBook.TALKBACK_EXPLORE].joinpath("android.log")
        self.tb_explore_android_events_log = self.audit_path_map[AddressBook.TALKBACK_EXPLORE].joinpath(
            "android_events.log")
        self.tb_explore_visited_nodes_path = self.audit_path_map[AddressBook.TALKBACK_EXPLORE].joinpath(
            "visited_nodes.jsonl")
        self.tb_explore_visited_nodes_screenshot = self.audit_path_map[AddressBook.TALKBACK_EXPLORE].joinpath(
            "visited_nodes.png")
        self.tb_explore_visited_nodes_gif = self.audit_path_map[AddressBook.TALKBACK_EXPLORE].joinpath(
            "visited_nodes.gif")
        # ----------- Audit: oversight_static ---------------
        self.audit_path_map[AddressBook.OVERSIGHT_STATIC] = self.snapshot_result_path.joinpath("OversightStatic")
        # ----------- Audit: Process Snapshot (OCR) ---------------
        self.audit_path_map[AddressBook.PROCESS_SCREENSHOT] = self.snapshot_result_path.joinpath("ProcessSnapshot")
        # ----------- Audit: Extract Actions ---------------
        self.audit_path_map[AddressBook.EXTRACT_ACTIONS] = self.snapshot_result_path.joinpath("ExtractActions")
        self.extract_actions_modes = {Actionables.All: 'all_actionables',
                                      Actionables.UniqueResource: 'unique_resource_actionables',
                                      Actionables.NA11y: 'na11y_actionables',
                                      Actionables.TBReachable: 'tb_reachable_actionables',
                                      Actionables.TBUnreachable: 'tb_unreachable_actionables',
                                      Actionables.Selected: 'selected_actionables',
                                      Actionables.Spanned: 'spanned_actionables',
                                      }
        self.extract_actions_nodes = {}
        self.extract_actions_screenshots = {}
        for mode, value in self.extract_actions_modes.items():
            self.extract_actions_nodes[mode] = self.audit_path_map[
                AddressBook.EXTRACT_ACTIONS].joinpath(f"{value}.jsonl")
            self.extract_actions_screenshots[mode] = self.audit_path_map[
                AddressBook.EXTRACT_ACTIONS].joinpath(f"{value}.png")
        # ----------- Audit: perform_actions ---------------
        self.audit_path_map[AddressBook.PERFORM_ACTIONS] = self.snapshot_result_path.joinpath("PerformActions")
        self.perform_actions_results_path = self.audit_path_map[AddressBook.PERFORM_ACTIONS].joinpath("results.jsonl")
        self.perform_actions_atf_issues_path = self.audit_path_map[AddressBook.PERFORM_ACTIONS].joinpath(
            "atf_elements.jsonl")
        self.perform_actions_atf_issues_screenshot = self.audit_path_map[AddressBook.PERFORM_ACTIONS].joinpath(
            "atf_elements.png")
        # ---------------------------------------------------
        # TODO: Needs to find a more elegant solution
        navigate_modes = [AddressBook.BASE_MODE, "tb_touch", "touch", "a11y_api"]
        self.mode_path_map = {}
        for mode in navigate_modes:
            self.mode_path_map[mode] = self.snapshot_result_path.joinpath(mode)
        self.initiated_path = self.snapshot_result_path.joinpath("initiated.txt")
        self.ovsersight_path = self.snapshot_result_path.joinpath("OS")
        # self.atf_issues_path = self.mode_path_map['exp'].joinpath("atf_issues.jsonl")
        self.action_path = self.snapshot_result_path.joinpath("action.jsonl")
        # self.all_element_screenshot = self.mode_path_map['exp'].joinpath("all_elements.png")
        # self.atf_issues_screenshot = self.mode_path_map['exp'].joinpath("atf_elements.png")
        # self.all_action_screenshot = self.mode_path_map['exp'].joinpath("all_actions.png")
        # self.valid_action_screenshot = self.mode_path_map['exp'].joinpath("valid_actions.png")
        # self.redundant_action_screenshot = self.mode_path_map['exp'].joinpath("redundant_actions.png")
        # self.visited_action_screenshot = self.mode_path_map['exp'].joinpath("visited_actions.png")
        # self.visited_elements_screenshot = self.mode_path_map['exp'].joinpath("visited_elements.png")
        # self.visited_elements_gif = self.mode_path_map['exp'].joinpath("visited_elements.gif")
        self.finished_path = self.snapshot_result_path.joinpath("finished.flag")
        # self.last_explore_log_path = self.snapshot_result_path.joinpath("last_explore.log")
        self.visited_elements_path = self.snapshot_result_path.joinpath("visited.jsonl")
        # self.valid_elements_path = self.snapshot_result_path.joinpath("valid_elements.jsonl")
        # self.tags_path = self.snapshot_result_path.joinpath("tags.jsonl")
        # self.s_possible_action_path = self.snapshot_result_path.joinpath("s_possible_action.jsonl")
        self.s_action_path = self.snapshot_result_path.joinpath("s_action.jsonl")
        # self.s_action_screenshot = self.mode_path_map['s_exp'].joinpath("all_actions.png")

    def initiate(self, recreate: bool = False):
        if not recreate:
            if self.initiated_path.exists():
                with open(self.initiated_path) as f:
                    content = f.read()
                if "STRUCTURE" in content:
                    return
        if self.snapshot_result_path.exists():
            shutil.rmtree(self.snapshot_result_path.absolute())
        self.snapshot_result_path.mkdir()
        # ------- Old -----
        self.ovsersight_path.mkdir()
        for path in self.mode_path_map.values():
            path.mkdir()
        self.action_path.touch()
        self.visited_elements_path.touch()
        self.s_action_path.touch()
        # ------- End Old -----
        with open(self.initiated_path, "w") as f:
            f.write("STRUCTURE\n")

    def initiate_talkback_explore_task(self):
        if self.audit_path_map[AddressBook.TALKBACK_EXPLORE].exists():
            shutil.rmtree(self.audit_path_map[AddressBook.TALKBACK_EXPLORE].resolve())
        self.audit_path_map[AddressBook.TALKBACK_EXPLORE].mkdir()

    def initiate_extract_actions_task(self):
        if self.audit_path_map[AddressBook.EXTRACT_ACTIONS].exists():
            shutil.rmtree(self.audit_path_map[AddressBook.EXTRACT_ACTIONS].resolve())
        self.audit_path_map[AddressBook.EXTRACT_ACTIONS].mkdir()

    def initiate_perform_actions_task(self):
        if self.audit_path_map[AddressBook.PERFORM_ACTIONS].exists():
            shutil.rmtree(self.audit_path_map[AddressBook.PERFORM_ACTIONS].resolve())
        self.audit_path_map[AddressBook.PERFORM_ACTIONS].mkdir()
        self.perform_actions_results_path.touch()
        modes = ["tb_touch", "touch", "a11y_api"]
        for mode in modes:
            path = self.mode_path_map[mode]
            if path.exists():
                shutil.rmtree(path.resolve())
            path.mkdir()

    def initiate_oversight_static_task(self):
        if self.audit_path_map[AddressBook.OVERSIGHT_STATIC].exists():
            shutil.rmtree(self.audit_path_map[AddressBook.OVERSIGHT_STATIC].resolve())
        self.audit_path_map[AddressBook.OVERSIGHT_STATIC].mkdir()

    def initiate_process_screenshot_task(self):
        if self.audit_path_map[AddressBook.PROCESS_SCREENSHOT].exists():
            shutil.rmtree(self.audit_path_map[AddressBook.PROCESS_SCREENSHOT].resolve())
        self.audit_path_map[AddressBook.PROCESS_SCREENSHOT].mkdir()

    def result_path(self) -> str:
        return self.snapshot_result_path.parent.parent.name

    def get_bm_log_path(self, extension: str = "") -> Path:
        log_name = self.snapshot_name()
        if extension:
            log_name += "_" + extension
        return self.snapshot_result_path.parent.joinpath(log_name + ".log")

    def app_name(self) -> str:
        return self.snapshot_result_path.parent.name

    def package_name(self) -> str:
        return self.app_name().split('(')[0]

    def snapshot_name(self) -> str:
        return self.snapshot_result_path.name

    def get_screenshot_path(self, mode: str, index: Union[int, str], extension: str = None,
                            should_exists: bool = False):
        file_name = f"{index}_{extension}.png" if extension else f"{index}.png"
        if not extension and mode == 's_exp':
            file_name = "INITIAL.png"
        return self._get_path(mode, file_name, should_exists)

    def get_layout_path(self, mode: str, index: int, should_exists: bool = False):
        if mode == 's_exp' or mode == AddressBook.BASE_MODE:
            index = 'INITIAL'
        return self._get_path(mode, f"{index}.xml", should_exists)

    def get_log_path(self, mode: str, index: int, extension: str = None, should_exists: bool = False):
        file_name = f"{index}_{extension}.log" if (
                extension is not None and extension != BLIND_MONKEY_TAG) else f"{index}.log"
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
        return self.audit_path_map[AddressBook.OVERSIGHT_STATIC].joinpath(f"{oac}.{extension}")

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
        tba_resource_id_to_action = {}
        apia_resource_id_to_action = {}
        for oac_node in oac_nodes:
            info = {}
            max_subseq_tb_element = None
            if oac_node.visible:
                for tb_xpath in tb_reachable_xpaths:
                    if oac_node.xpath.startswith(tb_xpath):
                        tb_node = Node.createNodeFromDict(tb_reachable_xpaths[tb_xpath])
                        if not bounds_included(tb_node.bounds, oac_node.bounds):
                            continue
                        if max_subseq_tb_element is None or len(max_subseq_tb_element['xpath']) < len(tb_xpath):
                            max_subseq_tb_element = tb_reachable_xpaths[tb_xpath]
            info['tbr'] = max_subseq_tb_element
            min_subseq_tb_action = None
            if info['tbr'] is not None:
                for tb_xpath in tb_actions_xpaths:
                    if tb_xpath.startswith(oac_node.xpath):
                        tb_node = Node.createNodeFromDict(tb_actions_xpaths[tb_xpath])
                        if not bounds_included(oac_node.bounds, tb_node.bounds):
                            continue
                        if min_subseq_tb_action is None or len(min_subseq_tb_action['xpath']) < len(tb_xpath):
                            min_subseq_tb_action = tb_actions_xpaths[tb_xpath]
            info['tba'] = min_subseq_tb_action
            if info['tba'] is not None and info['tba']['resource_id']:
                tba_resource_id_to_action[info['tba']['resource_id']] = info['tba']
            min_subseq_api_action = None
            for api_xpath in api_actions_xpaths:
                if api_xpath.startswith(oac_node.xpath):
                    api_node = Node.createNodeFromDict(api_actions_xpaths[api_xpath])
                    if not bounds_included(oac_node.bounds, api_node.bounds):
                        continue
                    if min_subseq_api_action is None or len(min_subseq_api_action['xpath']) < len(tb_xpath):
                        min_subseq_api_action = api_actions_xpaths[api_xpath]
            info['apia'] = min_subseq_api_action
            if info['apia'] is not None and info['apia']['resource_id']:
                tba_resource_id_to_action[info['apia']['resource_id']] = info['apia']
            oac_info_map[oac_node] = info
        for oac_node, info in oac_info_map.items():
            if info['tba'] is None and oac_node.resource_id in tba_resource_id_to_action:
                info['tba'] = tba_resource_id_to_action[oac_node.resource_id]
            if info['apia'] is None and oac_node.resource_id in apia_resource_id_to_action:
                info['apia'] = apia_resource_id_to_action[oac_node.resource_id]
        return oac_info_map


async def capture_current_state(address_book: AddressBook, device,
                                mode: str,
                                index: Union[int, str],
                                has_layout=True,
                                dumpsys: bool = False,
                                log_message_map: Optional[dict] = None,
                                use_adb_layout: bool = False) -> str:
    await asyncio.sleep(3)
    await save_screenshot(device, address_book.get_screenshot_path(mode, index))
    activity_name = await get_current_activity_name()
    with open(address_book.get_activity_name_path(mode, index), mode='w') as f:
        f.write(activity_name + "\n")

    layout = ""
    if has_layout:
        if use_adb_layout:
            layout = await adb_capture_layout()
        else:
            padb_logger = ParallelADBLogger(device)
            log_map, layout = await padb_logger.execute_async_with_log(capture_layout())
            with open(address_book.get_log_path(mode, index, extension="layout"), mode='w') as f:
                f.write(log_map[BLIND_MONKEY_TAG])
        with open(address_book.get_layout_path(mode, index), mode='w') as f:
            f.write(layout)

    if log_message_map:
        for tag, log_message in log_message_map.items():
            with open(address_book.get_log_path(mode, index, extension=tag), mode='w') as f:
                f.write(log_message)

    if dumpsys:
        windows = await get_windows()
        with open(address_book.get_log_path(mode, index, extension="WINDOWS"), mode='w') as f:
            f.write(windows + "\n")
        activities = await get_activities()
        with open(address_book.get_log_path(mode, index, extension="ACTIVITIES"), mode='w') as f:
            f.write(activities + "\n")

    return layout  # TODO: Remove it


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
            'node': node.toJSON() if use_detailed else None
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
                annotate_rectangle(source_img=exp_screenshot_path,
                                   target_img=self.address_book.get_screenshot_path('exp', action_index,
                                                                                    extension="edited"),
                                   bounds=[reg_action_result.bound],
                                   outline=(0, 255, 255),
                                   scale=15,
                                   width=15, )
        else:
            initial_path = self.address_book.get_screenshot_path('s_exp', 'INITIAL', should_exists=True)
            if initial_path is not None:
                if isinstance(tb_action_result, ExecutionResult):
                    annotate_rectangle(source_img=initial_path,
                                       target_img=self.address_book.get_screenshot_path('s_exp', action_index,
                                                                                        extension="edited"),
                                       bounds=[reg_action_result.bound, tb_action_result.bound],
                                       outline=[(255, 0, 255), (255, 255, 0)],
                                       width=[5, 15],
                                       scale=[1, 20])
                else:
                    annotate_rectangle(source_img=initial_path,
                                       target_img=self.address_book.get_screenshot_path('s_exp', action_index,
                                                                                        extension="edited"),
                                       bounds=[reg_action_result.bound],
                                       outline=(255, 0, 255),
                                       width=5,
                                       scale=1)
        new_action = {'index': action_index,
                      'element': element,
                      'tb_action_result': tb_action_result,
                      'reg_action_result': reg_action_result,
                      'areg_action_result': areg_action_result,
                      'node': None if node is None else node.toJSON(),
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
        return await capture_current_state(address_book=self.address_book,
                                           device=device,
                                           mode=mode,
                                           index=index,
                                           has_layout=has_layout,
                                           log_message_map=log_message_map)

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
