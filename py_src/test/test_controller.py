import unittest

from ppadb.device_async import DeviceAsync

from controller import create_controller, TalkBackTouchController, TalkBackDirectionalController, TalkBackAPIController, \
    A11yAPIController, TouchController, EnlargedDisplayController


class TestController(unittest.TestCase):
    def test_create_controller(self):
        device: DeviceAsync = None
        self.assertIsInstance(create_controller('tb_touch', device=device), TalkBackTouchController)
        self.assertIsInstance(create_controller('tb_api', device=device), TalkBackAPIController)
        self.assertIsInstance(create_controller('tb_dir', device=device), TalkBackDirectionalController)
        self.assertIsInstance(create_controller('a11y_api', device=device), A11yAPIController)
        self.assertIsInstance(create_controller('touch', device=device), TouchController)
        self.assertIsInstance(create_controller('enlarged', device=device), EnlargedDisplayController)
        self.assertIsNone(create_controller('abc', device=device))


