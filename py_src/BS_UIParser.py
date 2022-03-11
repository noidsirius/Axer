from enum import Enum
from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET
from collections import defaultdict
from itertools import cycle
from typing import List, Union
from pathlib import Path
from BS_models import Node, Screen
from PIL import Image, ImageDraw
import json


class Parser(ABC):

    @abstractmethod
    def parse_layout_tree(self, screen):
        pass


# Parses Virtual View Hierarchy as captured by blindsimmer UIAutomator
class BlindsimmerParser(Parser):
    @staticmethod
    def xml2node(xmlElement, screen):
        node = Node.createNodeFromXmlElement(xmlElement.attrib)
        node.set_screen(screen)
        return node

    def parse_layout_tree(self, screen: Screen) -> Node:
        def rec(node, father, screen: Screen):
            value = BlindsimmerParser.xml2node(node, screen)
            value.set_father(father)
            for child in node.findall("node"):
                value.add_child(rec(child, value, screen))
            return value

        with open(screen.layout_path, "r") as f:
            layout = f.read().replace("&", "&amp;")
        root_xml = ET.fromstring(layout).find('node')
        root_node = self.xml2node(root_xml, screen)

        for child in root_xml.findall('node'):
            root_node.add_child(rec(child, root_node, screen))
        screen.set_parsed_tree(root_node)
        return root_node


def calc_overlap(bounds, bounds1):
    dx = min(bounds[2], bounds1[2]) - max(bounds[0], bounds1[0])
    dy = min(bounds[3], bounds1[3]) - max(bounds[1], bounds1[1])

    ov = [max(bounds[0], bounds1[0]), max(bounds[1], bounds1[1]), min(bounds[2], bounds1[2]),
          min(bounds[3], bounds1[3])]
    if dx >= 0 and dy >= 0 and ov[0] < ov[2] and ov[1] < ov[3]:
        return ov
    return None


def get_leaves(node, leaves, condition):
    if len(node.children) == 0 and condition(node):
        leaves.append(node)
        return
    for child in node.children:
        get_leaves(child, leaves, condition)


def includes(bounds_parent, bounds_child):
    if bounds_child[2] <= bounds_parent[2] and bounds_child[3] <= bounds_parent[3] and \
            bounds_child[1] >= bounds_parent[1] and bounds_child[0] >= bounds_parent[0]:
        return True
    return False


def is_covered(node, area):
    if node.covered:
        return
    if includes(area, node.bounds):
        node.set_covered_descendants()
    else:
        for child in node.children:
            is_covered(child, area)


class ParseUI:
    def __init__(self, parser: Parser) -> None:
        self._parser = parser

    # check traversal order of the page to see which element is visible
    def is_front_view(self, screen: Screen, view1, view2):
        if view1.index < view2.index:
            return 1
        elif view2.index > view1.index:
            return 0
        return -1
        first = "{}:({}, {} - {}, {})".format(view1.class_name.split(".")[-1], view1.bounds[0], view1.bounds[1],
                                              view1.bounds[2], view1.bounds[3])
        second = "{}:({}, {} - {}, {})".format(view2.class_name.split(".")[-1], view2.bounds[0], view2.bounds[1],
                                               view2.bounds[2], view2.bounds[3])

        traversal_order = screen.get_traversal_order()
        if traversal_order.find(first) == traversal_order.find(second) == -1:
            return -1
        if traversal_order.find(first) < traversal_order.find(second):
            return 1
        elif traversal_order.find(second) > traversal_order.find(first):
            return 0
        return -1

    def get_specific_elements(self, tree_root, condition) -> List[Node]:

        specific_elements = []
        stack = [tree_root]
        while stack:
            current_node = stack.pop()
            if condition(current_node):
                specific_elements.append(current_node)
            for child in current_node.children:
                stack.append(child)

        return specific_elements

    def set_specific_elements(self, tree_root, condition, action):
        stack = [tree_root]
        while stack:
            current_node = stack.pop()
            if condition(current_node):
                action(current_node)
            for child in current_node.children:
                stack.append(child)

    def filter_invisibles(self, nodes):
        filtered_elements = []
        for node in nodes:
            if not node.visible or ("Layout" in node.class_name and len(node.children) == 0) or node.covered:
                continue
            filtered_elements.append(node)
        return filtered_elements

    def analyze_visibility(self, tree_root):
        sorted_children = sorted(tree_root.children, key=lambda x: x.drawing_order)
        svc = self.filter_invisibles(sorted_children)
        if len(svc) > 1:
            overlap_area = defaultdict(set)
            for i in range(len(svc) - 1, 0, -1):
                for j in range(0, i):
                    ov = calc_overlap(svc[i].bounds, svc[j].bounds)
                    if ov:
                        overlap_area[j].add(str(ov))

            for k, overlap_area in overlap_area.items():
                for area in overlap_area:
                    is_covered(svc[k], [int(x) for x in area[1:-1].split(",")])

        for n in svc:
            if not n.covered:
                self.analyze_visibility(n)

    def annotate(self, screen: Screen, nodes, name: str = None, color='red', debug=False):
        if name is None:
            name = color
        postfix = ""
        if len(nodes) == 0 and not debug:
            postfix = "-nochange"
        if debug:
            postfix = "-debug"
        image = Image.open(screen.screenshot_path)
        img_draw = ImageDraw.Draw(image)

        for node in nodes:
            img_draw.rectangle(node.bounds, outline=color, width=3)
        image.save(
            screen.screenshot_path[0:screen.screenshot_path.rfind(".")] + "-{}-annotated{}.png".format(name, postfix))


class OAC(Enum):  # Overly Accessible Condition
    BELONGED = 1
    OUT_OF_BOUNDS = 2
    COVERED = 3
    ZERO_AREA = 4
    INVISIBLE = 5
    CAMOUFLAGED = 6
    CONDITIONAL_DISABLED = 7
    INCONSISTENT_ABILITIES = 8


def statice_analyze(layout_path: Union[str, Path], screenshot_path: Union[str, Path], pkg_name: str) -> dict:
    if isinstance(layout_path, str):
        layout_path = Path(layout_path)
    if isinstance(screenshot_path, str):
        screenshot_path = Path(screenshot_path)
    bs_parser = BlindsimmerParser()
    parseUI = ParseUI(bs_parser)
    screen = Screen(str(layout_path), str(screenshot_path), pkg_name)
    if not screen.tree:
        bs_parser.parse_layout_tree(screen)
    tree_root = screen.tree
    parseUI.analyze_visibility(tree_root)
    [min_x, min_y, max_x, max_y] = tree_root.bounds
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

    colors = ['red', 'fuchsia', 'blue']
    node_to_oac_map = defaultdict(list)
    oac_count = {}
    for (key, query), color in zip(oa_conditions.items(), cycle(colors)):
        oa_nodes = parseUI.get_specific_elements(tree_root,
                                                 condition=lambda node: node.potentially_data_or_function() and
                                                                        query(node))
        parseUI.annotate(screen, oa_nodes, name=key, color=color)
        oac_count[key] = len(oa_nodes)
        for node in oa_nodes:
            node_to_oac_map[node].append(key)
    result_path = layout_path.parent.joinpath("oae.jsonl")
    with open(result_path, "w") as f:
        for node, oacs in node_to_oac_map.items():
            entry = {'node': json.loads(node.toJSONStr()), 'OACs': [str(x) for x in oacs]}
            f.write(f"{json.dumps(entry)}\n")
    return oac_count


if __name__ == '__main__':
    import os

    import argparse

    argparser = argparse.ArgumentParser(description='provide the argument')
    argparser.add_argument('--root', default="../tmp", type=str)
    argparser.add_argument('--pkg', required=True, type=str)
    argparser.add_argument('--command', type=str)
    argparser.add_argument('--bulk', default=False)
    args = argparser.parse_args()
    print(args.command)

    p = ParseUI(BlindsimmerParser())

    if args.bulk:
        apps = [a[1] for a in os.walk(args.root)]
        apps = apps[0]
    else:
        apps = [args.pkg]

    for pkg_name in apps:
        app_path = Path(args.root).joinpath(pkg_name)
        scenarios = [a[1] for a in os.walk(app_path)]
        scenarios = scenarios[0]
        print(f"App: {pkg_name}")
        for scenario in scenarios:
            print(f"\tScenario: {scenario}")
            scenario_path = app_path.joinpath(scenario)
            report = statice_analyze(scenario_path.joinpath("uiut-a11y.xml"), scenario_path.joinpath("uiut.png"),
                                     pkg_name)
            for key, value in report.items():
                print(f"\t\t#{key}: {value}")
