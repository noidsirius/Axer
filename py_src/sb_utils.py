import argparse
import json
import logging
from collections import defaultdict
from itertools import cycle
from pathlib import Path
from typing import Union, List

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
    [min_x, min_y, max_x, max_y] = nodes[0].bounds

    oa_conditions = {
        OAC.BELONGED: lambda node: node.pkg_name != pkg_name,
        OAC.OUT_OF_BOUNDS: lambda node: ((max_x < node.bounds[0] or node.bounds[0] < min_x) or
                                         (max_x < node.bounds[2] or node.bounds[2] < min_x) or
                                         (max_y < node.bounds[1] or node.bounds[1] < min_y) or
                                         (max_y < node.bounds[3] or node.bounds[3] < min_y)),
        OAC.COVERED: lambda node: node.covered,
        OAC.ZERO_AREA: lambda node: (node.bounds[2] - node.bounds[0]) * (node.bounds[3] - node.bounds[1]) == 0,
        OAC.INVISIBLE: lambda node: not node.visible,
        OAC.CONDITIONAL_DISABLED: lambda node: not node.enabled and
                                               (node.clickable or node.long_clickable or node.focusable),
        OAC.INCONSISTENT_ABILITIES: lambda node: (not node.clickable and "16" in node.a11y_actions),  # TODO
                                                 # or (not node.long_clickable and "32" in node.a11y_actions)
        OAC.AD: lambda node: node.is_ad
    }
    oa_conditions[OAC.CAMOUFLAGED] = lambda node: node.text == node.content_desc == "" and \
                                                  node.class_name == "android.widget.TextView" and \
                                                  node.visible and \
                                                  not oa_conditions[OAC.OUT_OF_BOUNDS] and \
                                                  not oa_conditions[OAC.ZERO_AREA]

    node_to_oac_map = defaultdict(list)
    oac_count = {}
    for key, query in oa_conditions.items():
        if key != OAC.AD:
            oa_nodes = [node for node in nodes if not node.is_ad and node.potentially_data_or_function() and query(node)]
        else:
            oa_nodes = [node for node in nodes if node.potentially_data_or_function() and query(node)]

        annotate_elements(screenshot_path,
                          address_book.get_os_result_path(key, extension='png'),
                          oa_nodes)
        oac_count[key] = len(oa_nodes)
        with open(address_book.get_os_result_path(key), "w") as f:
            for node in oa_nodes:
                if key != OAC.AD:
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
