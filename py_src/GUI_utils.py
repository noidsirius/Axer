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


def get_elements(query: Callable[[etree.Element], bool] = None) -> List:
    dom = asyncio.run(capture_layout())
    dom_utf8 = dom.encode('utf-8')
    parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
    tree = etree.fromstring(dom_utf8, parser)
    if tree is None:
        return []
    commands = []
    for i, x in enumerate(tree.getiterator()):
        if query is not None and not query(x):
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
                }
        for k in info:
            if type(info[k]) == str and len(info[k]) == 0:
                info[k] = 'null'
        command = json.loads(json.dumps(info))
        commands.append(command)
    return commands
