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
        path = get_xpath(node.getparent()) + path
    return path
