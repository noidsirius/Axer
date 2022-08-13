import json
import unittest

from genymotion_utils import RecipeInfo, GenymotionInstance

recipe_dict = """{
            "uuid": "b1e51193-4db8-43f7-b7cd-ae35eebb6bca",
            "name": "Custom Phone",
            "android_version": "4.4.4",
            "screen_width": 768,
            "screen_height": 1280,
            "screen_density": 320,
            "screen": "768 x 1280 dpi 320",
            "source": "genymotion"
        }"""

instance_dict = """{
        "uuid": "62ec330e-47d2-4a6b-939f-122718505329",
        "name": "test",
        "created_at": "2021-05-29T11:54:35.000Z",
        "state": "ONLINE",
        "adbtunnel_state": "DISCONNECTED",
        "adb_serial": "0.0.0.0",
        "adb_serial_port": 0,
        "recipe": {
            "uuid": "b9cf7b2c-4d11-4777-97c7-29d3b5c68d59",
            "name": "Samsung Galaxy S8",
            "android_version": "8.0",
            "screen_width": 1440,
            "screen_height": 2960,
            "screen_density": 480,
            "screen": "1440 x 2960 dpi 480",
            "source": "genymotion"
        }
    }"""


class TestGenymotion(unittest.TestCase):
    def test_genymotion_objects(self):
        recipe = RecipeInfo(**json.loads(recipe_dict))
        self.assertEqual("b1e51193-4db8-43f7-b7cd-ae35eebb6bca", recipe.uuid)
        self.assertEqual("Custom Phone", recipe.name)
        self.assertEqual(768, recipe.screen_width)
        self.assertEqual(1280, recipe.screen_height)
        instance = GenymotionInstance(**json.loads(instance_dict))
        self.assertEqual("62ec330e-47d2-4a6b-939f-122718505329", instance.uuid)
        self.assertEqual("b9cf7b2c-4d11-4777-97c7-29d3b5c68d59", instance.recipe.uuid)
        self.assertTrue(instance.is_online())
        self.assertIsNone(instance.get_adb_device_name())


