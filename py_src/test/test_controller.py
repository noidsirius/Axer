import unittest

from controller import create_controller, TalkBackTouchController, TalkBackDirectionalController, TalkBackAPIController, \
    A11yAPIController, TouchController


class TestController(unittest.TestCase):
    def test_create_controller(self):
        device_name = "dummy"
        self.assertIsInstance(create_controller('tb_touch', device_name=device_name), TalkBackTouchController)
        self.assertIsInstance(create_controller('tb_api', device_name=device_name), TalkBackAPIController)
        self.assertIsInstance(create_controller('tb_dir', device_name=device_name), TalkBackDirectionalController)
        self.assertIsInstance(create_controller('a11y_api', device_name=device_name), A11yAPIController)
        self.assertIsInstance(create_controller('touch', device_name=device_name), TouchController)
        self.assertIsNone(create_controller('abc', device_name=device_name))


