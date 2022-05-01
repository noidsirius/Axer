import argparse
import json
import logging
from collections import defaultdict
from itertools import cycle
from pathlib import Path
from typing import Union, List, Tuple

from GUI_utils import NodesFactory, Node
from results_utils import OAC, AddressBook, get_snapshot_paths
from utils import annotate_elements

logger = logging.getLogger(__name__)


def statice_analyze(layout_path: Union[str, Path],
                    screenshot_path: Union[str, Path],
                    address_book: AddressBook) -> List[Node]:
    if isinstance(layout_path, str):
        layout_path = Path(layout_path)
    if isinstance(screenshot_path, str):
        screenshot_path = Path(screenshot_path)

    pkg_name = address_book.app_name()  # TODO: It's not always correct

    nodes = NodesFactory() \
        .with_layout_path(layout_path) \
        .with_ad_detection() \
        .with_xpath_pass() \
        .with_covered_pass() \
        .build()
    screen_bounds = nodes[0].bounds

    oa_conditions = {
        OAC.P1_OUT_OF_BOUNDS: lambda node: node.is_out_of_bounds(screen_bounds) and node.is_valid_bounds(),
        OAC.P2_COVERED: lambda node: node.covered,
        OAC.P3_ZERO_AREA: lambda node: node.area() == 0,
        OAC.P4_AINVISIBLE: lambda node: not node.visible,
        OAC.P5_BELONGS: lambda node: not node.belongs(pkg_name),
        OAC.P6_INVALID_BOUNDS: lambda node: node.bounds[2] < node.bounds[0] or node.bounds[3] < node.bounds[1],
        OAC.A2_CONDITIONAL_DISABLED: lambda node: not node.enabled,
        OAC.A3_CAMOUFLAGED: lambda node: (node.text == node.content_desc == "") and
                                         node.class_name == "android.widget.TextView" and
                                         node.visible and
                                         not node.is_out_of_bounds(screen_bounds) and
                                         node.is_valid_bounds(),
        OAC.O_AD: lambda node: node.is_ad
    }
    oa_conditions[OAC.A1_PINVISIBLE] = lambda node: any(oa_conditions[oac](node) for oac in OAC if oac.name.startswith("P"))
    # P_Map = {}
    # for i in range(1, 7):
    #     P_Map[i] = [oac for oac in OAC if oac.name.startswith(f"P{str(i)}")][0]
    # OAC_MAP = {}
    # for oac in OAC:
    #     OAC_MAP[oac.name] = oac
    # for i in range(1, 7):
    #     for j in range(i+1, 7):
    #         key = f"O_P{i}{j}"
    #         oac = OAC_MAP[key]
    #         oa_conditions[oac] = lambda node, i=i, j=j: oa_conditions[P_Map[i]](node) and oa_conditions[P_Map[j]](node)

    node_to_oac_map = defaultdict(list)
    oac_count = {}
    for key, query in oa_conditions.items():
        queries = [query]
        if key.name.startswith("P") or key.name.startswith("O_P"):
            queries.append(lambda node: not node.is_ad and node.potentially_data())
        elif key.name.startswith("A"):
            queries.append(lambda node: not node.is_ad and node.potentially_function())
        else:
            queries.append(lambda node: node.potentially_data() or node.potentially_function())
        oa_nodes = [node for node in nodes if all(q(node) for q in queries)]
        annotate_elements(screenshot_path,
                          address_book.get_os_result_path(key, extension='png'),
                          oa_nodes)
        oac_count[key] = len(oa_nodes)
        logger.info(f"{key}: {len(oa_nodes)}")
        with open(address_book.get_os_result_path(key), "w") as f:
            for node in oa_nodes:
                if key != OAC.O_AD:
                    node_to_oac_map[node].append(key)
                f.writelines(f"{node.toJSONStr()}\n")

    annotate_elements(screenshot_path,
                      address_book.get_os_result_path(extension='png'),
                      list(node_to_oac_map.keys()))

    result_path = address_book.get_os_result_path()
    with open(result_path, "w") as f:
        for node, oacs in node_to_oac_map.items():
            entry = {'node': json.loads(node.toJSONStr()), 'OACs': [str(x) for x in oacs]}
            f.write(f"{json.dumps(entry)}\n")

    return list(node_to_oac_map.keys())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot-path', type=str, help="Path of the snapshot's result")
    parser.add_argument('--app-path', type=str, help="Path of the app's result")
    parser.add_argument('--result-path', type=str, help="Path of the result's path")
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--override', action='store_true')
    parser.add_argument('--remove', action='store_true')
    parser.add_argument('--log-path', type=str, help="Path where logs are written")
    args = parser.parse_args()

    if args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    if args.log_path:
        logging.basicConfig(level=level,
                            handlers=[
                                logging.FileHandler(args.log_path, mode='w'),
                                logging.StreamHandler()])
    else:
        logging.basicConfig(level=level)

    for snapshot_path in get_snapshot_paths(args.result_path, args.app_path, args.snapshot_path):
        address_book = AddressBook(snapshot_path)
        layout_path = address_book.get_layout_path('exp', 'INITIAL', should_exists=True)
        screenshot_path = address_book.get_screenshot_path('exp', 'INITIAL', should_exists=True)
        if layout_path and screenshot_path:
            statice_analyze(layout_path, screenshot_path, address_book)
