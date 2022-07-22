import unittest

from GUI_utils import Node
from command import Command, ClickCommand, NextCommand, PreviousCommand, SelectCommand, BackCommand, SleepCommand, \
    create_command_from_dict


class TestCommand(unittest.TestCase):
    def test_command_constructors(self):
        self.assertEqual("NOP", Command().action)
        unknown_command = create_command_from_dict({'action': 'unknown', 'attribute': 34})
        self.assertEqual("NOP", unknown_command.action)

    def test_click_command(self):
        node = Node(text="dummy_text", checked=True)
        click_command = ClickCommand(node=node)
        self.assertEqual("click", click_command.action)
        self.assertEqual("dummy_text", click_command.target.text)
        self.assertTrue(click_command.target.checked)
        click_command = create_command_from_dict({'action': 'click', 'target': node.toJSON()})
        self.assertIsInstance(click_command, ClickCommand)
        self.assertEqual("dummy_text", click_command.target.text)
        self.assertTrue(click_command.target.checked)

    def test_navigate_commands(self):
        self.assertEqual("next", NextCommand().action)
        self.assertEqual("previous", PreviousCommand().action)
        self.assertEqual("select", SelectCommand().action)
        self.assertEqual("back", BackCommand().action)
        self.assertIsInstance(create_command_from_dict({'action': 'next'}), NextCommand)
        self.assertIsInstance(create_command_from_dict({'action': 'previous'}), PreviousCommand)
        self.assertIsInstance(create_command_from_dict({'action': 'select'}), SelectCommand)
        self.assertIsInstance(create_command_from_dict({'action': 'back'}), BackCommand)

    def test_sleep_command(self):
        sleep_command = SleepCommand(delay=200)
        self.assertEqual("sleep", sleep_command.action)
        self.assertEqual(200, sleep_command.delay)
        self.assertEqual(0, SleepCommand().delay)
        self.assertEqual(0, SleepCommand(delay=-10).delay)
        sleep_command = create_command_from_dict({'action': 'sleep', 'delay': '300'})
        self.assertIsInstance(sleep_command, SleepCommand)
        self.assertEqual(300, sleep_command.delay)


