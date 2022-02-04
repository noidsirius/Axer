import logging
from typing import Callable, List
import json
import asyncio
from lxml import etree
from adb_utils import capture_layout


logger = logging.getLogger(__name__)


def get_element_class(node):
    # for XPATH we have to count only for nodes with same type!
    length = 0
    index = -1
    if node.getparent() is not None:
        for x in node.getparent().getchildren():
            if node.attrib.get('class', 'NONE1') == x.attrib.get('class', 'NONE2'):
                length += 1
            if x == node:
                index = length
    if length > 1:
        return f"{node.attrib.get('class', '')}[{index}]"
    return node.attrib.get('class', '')


def get_xpath(node):
    node_class_name = get_element_class(node)
    path = '/' + node_class_name if node_class_name != "" else ""
    if node.getparent() is not None and node.getparent().attrib.get('class', 'NONE') != 'hierarchy':
        path = get_xpath(node.getparent()) + path
    return path


def are_equal_elements(element1: dict, element2: dict) -> bool:
    """
    Determines if two elements are equal. The focused attribute is excluded since it depends on TalkBack's state
    :param element1:  A GUI element with various attributes such as resourceId
    :param element2: Another GUI element
    :return:
    """
    if element1.keys() != element2.keys():
        return False
    for key in element1:
        if key in 'focused':
            continue
        if element1[key] != element2[key]:
            return False
    return True


def get_elements(dom: str, filter_query: Callable[[etree.Element], bool] = None) -> List:
    """
    Given a DOM of an Android layout, creates the GUI elements that passes the filter query

    :param dom: The DOM structure of the layout
    :param filter_query: An optional function inputs a :class:`etree.Element` and
            returns if the element should be added to the output
    :return: List of GUI elements in `dom` that passes the `filter_query`
    """
    dom_utf8 = dom.encode('utf-8')
    parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
    tree = etree.fromstring(dom_utf8, parser)
    if tree is None:
        return []
    commands = []
    for i, x in enumerate(tree.getiterator()):
        if filter_query is not None and not filter_query(x):
            continue
        x_attrs = dict(x.attrib.items())
        info = {'resourceId': x_attrs.get('resource-id', ''),
                'contentDescription': x_attrs.get('content-desc', ''),
                'text': x_attrs.get('text', ''),
                'class': x_attrs.get('class', ''),
                'xpath': get_xpath(x),
                'located_by': 'xpath',
                'skip': False,
                'action': 'click',
                'naf': x_attrs.get('NAF', False),
                'bounds': x_attrs.get('bounds', ""),
                'checkable': x_attrs.get('checkable', ''),
                'checked': x_attrs.get('checked', ''),
                'clickable': x_attrs.get('clickable', ''),
                'enabled': x_attrs.get('enabled', ''),
                'focusable': x_attrs.get('focusable', ''),
                'focused': x_attrs.get('focused', ''),
                }
        for k in info:
            if type(info[k]) == str and len(info[k]) == 0:
                info[k] = 'null'
        command = json.loads(json.dumps(info))
        commands.append(command)
    return commands


def get_actions_from_layout(layout: str) -> List[dict]:
    important_elements = get_elements(layout,
                                      filter_query=lambda x: x.attrib.get('clickable', 'false') == 'true'
                                                             or x.attrib.get('NAF', 'false') == 'true')
    visited_resource_ids = set()
    refined_list = []
    for e in important_elements:
        if e['resourceId'] and e['resourceId'] != 'null':
            if e['resourceId'] in visited_resource_ids:
                continue
            visited_resource_ids.add(e['resourceId'])
        refined_list.append(e)
    return refined_list
