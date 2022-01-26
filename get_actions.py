import sys
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re
import json
from lxml import etree

xml_path = sys.argv[1]

def get_element(node):
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
    node_class_name = get_element(node)
    path = '/' + node_class_name if node_class_name != "" else ""
    if node.getparent() is not None and node.getparent().attrib.get('class', 'NONE') != 'hierarchy':
        path = get_xpath(node.getparent()) +path
    return path



import subprocess
with open(xml_path) as f:
    dom = f.read()
soup = BeautifulSoup(dom, 'lxml')
dom_utf8 = dom.encode('utf-8')
parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
tree = etree.fromstring(dom_utf8, parser)
for i,x in enumerate(tree.getiterator()):
        x_attrs = dict(x.attrib.items())
        if len(x.getchildren()) == 0:
            if x_attrs.get('displayed', 'true') == 'false':
                continue
            info = {'class': x_attrs.get('class', ''), 'text': x_attrs.get('text', ''), 'contentDescription': x_attrs.get('content-desc', ''),
                 'resourceId': x_attrs.get('resource-id', '')}
            info['xpath'] = get_xpath(x)
            info['located_by'] = 'xpath'
            info['skip'] = False
            info['action'] = 'click'
            # command = "'"+str(json.dumps(info))+"'"
            command = str(json.dumps(info))
            print(command)
            # EXECUTOR = "REG"
            # bashCommand = ["./bm_run_reg.sh", "yelp_rate", command, EXECUTOR]
            # print(i, bashCommand)
            # # break
            # process = subprocess.Popen(bashCommand, stdout=subprocess.PIPE)
            # output, error = process.communicate()
            # with open(f"result/{EXECUTOR}/{i}.txt", "w") as f:
            #     f.write(f"===Output===\n{output.decode('utf-8') if output else 'NONE'}\n===Error===\n{error.decode('utf-8') if error else 'NONE'}")
            # process = subprocess.Popen(f"cp {EXECUTOR}.txt result/{EXECUTOR}/{i}.xml".split(), stdout=subprocess.PIPE)
            # output, error = process.communicate()
