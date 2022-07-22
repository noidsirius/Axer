import unittest

from GUI_utils import Node
import json

node1_json_str = '{"a11y_actions": ["4", "8", "64", "16908342"], "action": "click", "bounds": [540, 214, 540, 281], "checkable": false, "checked": false, "class_name": "android.widget.TextView", "clickable": false, "clickable_span": false, "content_desc": "my_content", "context_clickable": false, "covered": false, "drawing_order": 1, "enabled": true, "focusable": false, "focused": false, "important_for_accessibility": true, "index": 0, "invalid": false, "is_ad": false, "located_by": "xpath", "long_clickable": false, "naf": false, "pkg_name": "au.gov.nsw.newcastle.app.android", "resource_id": "my_res", "skip": false, "text": "my_text", "visible": false, "xpath": "/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.view.ViewGroup/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.TextView"}'


class TestNode(unittest.TestCase):
    def test_node_constructor(self):
        self.assertTrue(Node().is_none())
        self.assertTrue(Node.createNodeFromDict({}).is_none())
        node = Node.createNodeFromDict(json.loads(node1_json_str))
        self.assertEqual("my_text", node.text)
        self.assertEqual("my_res", node.resource_id)
        self.assertEqual("my_content", node.content_desc)
        self.assertEqual("android.widget.TextView", node.class_name)
        self.assertTrue(node.important_for_accessibility)
        self.assertListEqual(["4", "8", "64", "16908342"], node.a11y_actions)
        self.assertEqual("au.gov.nsw.newcastle.app.android", node.pkg_name)

