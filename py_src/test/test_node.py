import unittest

from GUI_utils import Node
import json

node1_json_str = '{"a11y_actions": ["4", "8", "64", "16908342"], "action": "click", "bounds": [540, 214, 540, 281], "checkable": false, "checked": false, "class_name": "android.widget.TextView", "clickable": false, "clickable_span": false, "content_desc": "my_content", "context_clickable": false, "covered": false, "drawing_order": 1, "enabled": true, "focusable": false, "focused": false, "important_for_accessibility": true, "index": 0, "invalid": false, "is_ad": false, "located_by": "xpath", "long_clickable": false, "naf": false, "pkg_name": "au.gov.nsw.newcastle.app.android", "resource_id": "my_res", "skip": false, "text": "my_text", "visible": false, "xpath": "/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.view.ViewGroup/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.TextView"}'


# TODO: Add a node which is captured from Latte


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
        self.assertListEqual([4, 8, 64, 16908342], node.a11y_actions)
        self.assertEqual("au.gov.nsw.newcastle.app.android", node.pkg_name)
        # Remove /hierarchy from xpath
        self.assertEqual("/a/b", Node(xpath="/hierarchy/a/b").xpath)

    def test_android_layout_compatibility(self):
        node_json = {
            "class": "c1",
            "resource-id": "r1",
            "content-desc": "c2",
            "package": "p1",
            "clickableSpan": "true",
            "long-clickable": "false",
            "contextClickable": True,
            "NAF": False,
            "importantForAccessibility": True,
            "actionList": "1-2-4",
            "drawingOrder": "3"
        }
        node = Node.createNodeFromDict(node_json)
        self.assertEqual("c1", node.class_name)
        self.assertEqual("r1", node.resource_id)
        self.assertEqual("c2", node.content_desc)
        self.assertEqual("p1", node.pkg_name)
        self.assertTrue(node.clickable_span)
        self.assertFalse(node.long_clickable)
        self.assertTrue(node.context_clickable)
        self.assertFalse(node.naf)
        self.assertTrue(node.important_for_accessibility)
        self.assertListEqual([1, 2, 4], node.a11y_actions)
        self.assertEqual(3, node.drawing_order)

    def test_practically_equal(self):
        node1 = Node.createNodeFromDict(json.loads(node1_json_str))
        node2 = Node.createNodeFromDict(json.loads(node1_json_str))
        node2.focused = not node1.focused
        node2.bounds = (10, 10, 20, 20)
        node2.index = node1.index + 10
        node2.drawing_order = node1.drawing_order + 5
        node2.a11y_actions.append(32)
        self.assertTrue(node1.practically_equal(node2))
        node2.text = "something else"
        self.assertFalse(node1.practically_equal(node2))

    def test_bounds(self):
        node1 = Node(bounds=(1, 2, 3, 4))
        self.assertEqual((1, 2, 3, 4), node1.bounds)
        self.assertTrue(node1.is_valid_bounds())
        node2 = Node.createNodeFromDict({"bounds": "[10,20][110,220]"})
        self.assertEqual((10, 20, 110, 220), node2.bounds)
        self.assertTrue(node2.is_valid_bounds())
        self.assertFalse(Node(bounds=(10, 10, 5, 15)).is_valid_bounds())
        self.assertFalse(Node(bounds=(10, 10, 15, 5)).is_valid_bounds())
        self.assertFalse(Node(bounds=(10, 10, 5, 5)).is_valid_bounds())
        normalized_bounds = node2.get_normalized_bounds((0, 10, 500, 410))
        self.assertEqual((10/500, 10/400, 110/500, 210/400), normalized_bounds)

