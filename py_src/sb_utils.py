import json
from collections import defaultdict
from itertools import cycle
from pathlib import Path
from typing import Union

from GUI_utils import NodesFactory
from results_utils import OAC, AddressBook
from utils import annotate_elements


def statice_analyze(layout_path: Union[str, Path],
                    screenshot_path: Union[str, Path],
                    address_book: AddressBook) -> dict:

    if isinstance(layout_path, str):
        layout_path = Path(layout_path)
    if isinstance(screenshot_path, str):
        screenshot_path = Path(screenshot_path)

    pkg_name = address_book.app_name()  # TODO: It's not always correct

    nodes = NodesFactory() \
        .with_layout_path(layout_path) \
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
        OAC.INCONSISTENT_ABILITIES: lambda node: (not node.clickable and "16" in node.a11y_actions) or
                                                 (not node.long_clickable and "32" in node.a11y_actions) or
                                                 (not node.focusable and "64" in node.a11y_actions)
    }
    oa_conditions[OAC.CAMOUFLAGED] = lambda node: node.text == node.content_desc == "" and \
                                                  node.class_name == "android.widget.TextView" and \
                                                  node.visible and \
                                                  not oa_conditions[OAC.OUT_OF_BOUNDS] and \
                                                  not oa_conditions[OAC.ZERO_AREA]

    node_to_oac_map = defaultdict(list)
    oac_count = {}
    for key, query in oa_conditions.items():
        oa_nodes = [node for node in nodes if node.potentially_data_or_function() and query(node)]

        annotate_elements(screenshot_path,
                          address_book.get_sb_result_path(key, extension='png'),
                          oa_nodes)
        oac_count[key] = len(oa_nodes)
        with open(address_book.get_sb_result_path(key, extension='jsonl'), "w") as f:
            for node in oa_nodes:
                node_to_oac_map[node].append(key)
                f.writelines(f"{node.toJSONStr()}\n")

    result_path = address_book.sb_path.joinpath("oae.jsonl")
    with open(result_path, "w") as f:
        for node, oacs in node_to_oac_map.items():
            entry = {'node': json.loads(node.toJSONStr()), 'OACs': [str(x) for x in oacs]}
            f.write(f"{json.dumps(entry)}\n")

    return oac_count