import re
import json
from typing import Tuple, List, Union
from xml.etree.ElementTree import Element as XMLElement

""" The classes of objects that exist in captured layouts of LabelDroid dataset which are captured by STOAT """


class Node:
    @staticmethod
    def createNodeFromXmlElement(xmlElement: XMLElement) -> 'Node':
        return Node(**xmlElement)

    def __init__(self,
                 index: Union[int, str] = -1,
                 text: str = "",
                 class_name: str = "",
                 resource_id: str = "",
                 content_desc: str = "",
                 visible: Union[bool, str] = True,
                 clickable: Union[bool, str] = False,
                 long_clickable: Union[bool, str] = False,
                 enabled: Union[bool, str] = False,
                 focusable: Union[bool, str] = False,
                 important_for_accessibility: Union[bool, str] = False,
                 bounds: Union[Tuple[int, int, int, int], str] = (0, 0, 0, 0),
                 drawing_order: Union[int, str] = -1,
                 a11y_actions: Union[List[int], str] = None,
                 pkg_name: str = "",
                 **kwargs):
        class_name = kwargs.get('class', class_name)
        resource_id = kwargs.get('resourceId', resource_id)
        content_desc = kwargs.get('content-desc', content_desc)
        important_for_accessibility = kwargs.get('importantForAccessibility', important_for_accessibility)
        a11y_actions = kwargs.get('actionList', a11y_actions)
        drawing_order = kwargs.get('drawingOrder', drawing_order)
        pkg_name = kwargs.get('package', pkg_name)

        if isinstance(index, str):
            index = int(index)
        if isinstance(visible, str):
            visible = visible == 'true'
        if isinstance(clickable, str):
            clickable = clickable == 'true'
        if isinstance(long_clickable, str):
            long_clickable = long_clickable == 'true'
        if isinstance(clickable, str):
            clickable = clickable == 'true'
        if isinstance(enabled, str):
            enabled = enabled == 'true'
        if isinstance(focusable, str):
            focusable = focusable == 'true'
        if isinstance(important_for_accessibility, str):
            important_for_accessibility = important_for_accessibility == 'true'
        if isinstance(bounds, str):
            bounds = bounds.strip()
            if not re.search(r"\[\d+,\d+]\[\d+,\d+]", bounds):
                raise Exception(f"Problem with bounds! {bounds}")
            bounds = tuple([int(x) for x in bounds.replace("][", ",")[1:-1].split(",")])
        if isinstance(drawing_order, str):
            drawing_order = int(drawing_order)
        if a11y_actions is None:
            a11y_actions = []
        elif isinstance(a11y_actions, str):
            a11y_actions = a11y_actions.split("-")
        self.index = index
        self.class_name = class_name
        self.text = text
        self.resource_id = resource_id
        self.content_desc = content_desc
        self.visible = visible
        self.clickable = clickable
        self.long_clickable = long_clickable
        self.enabled = enabled
        self.focusable = focusable
        self.important_for_accessibility = important_for_accessibility
        self.bounds = bounds
        self.drawing_order = drawing_order
        self.a11y_actions = a11y_actions
        self.pkg_name = pkg_name
        # --- Extra ----
        self.screen = None
        self.father = None
        self.children = []
        self.covered = False
        self.id = None  # TODO

    def set_id(self, id):
        self.id = id

    def set_screen(self, screen: 'Screen'):
        self.screen = screen

    def set_father(self, father):
        self.father = father

    def add_child(self, child):
        self.children.append(child)

    def potentially_data_or_function(self):
        return self.clickable or \
               self.long_clickable or \
               self.text or \
               self.content_desc or \
               set(self.a11y_actions).intersection({"16", "32"})

    def set_covered_descendants(self):
        self.covered = True
        for child in self.children:
            child.set_covered_descendants()

    def toJSONStr(self) -> str:
        return json.dumps(self,
                          default=lambda o: {k: v for (k, v) in o.__dict__.items() if k not in ['screen', 'father', 'children']},
                          sort_keys=True)

    def __str__(self):
        a = {"index": self.index, "class": self.class_name, "text": self.text,
             "bounds": "[{},{}][{},{}]".format(self.bounds[0], self.bounds[1], self.bounds[2], self.bounds[3]),
             "clickable": self.clickable, "enabled": self.enabled, "content-desc": self.content_desc,
             "focusable": self.focusable, "importantForAccessibility": self.important_for_accessibility,
             "covered": self.covered, "drawing_order": self.drawing_order, "resource-id": self.resource_id,
             "actionList": self.a11y_actions}
        return json.dumps(a)


class Screen:
    def __init__(self, layout_path, screenshot_path, pkg_name, activity_name=None, rotation=None):
        self.talkback_path = None
        self.layout_path = layout_path
        self.pkg_name = pkg_name
        self.activity_name = activity_name
        self.rotation = rotation
        self.tree = None
        self.screenshot_path = screenshot_path
        self.traversal_order = None

    def set_parsed_tree(self, root):
        self.tree = root

    def get_traversal_order(self, talkback_path):
        if not self.traversal_order:
            with open(talkback_path, "r") as f:
                data = f.read()
                self.traversal_order = data.split("------------Node tree traversal order------------")[1]
        return self.traversal_order
