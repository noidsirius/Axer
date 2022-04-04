import json
from typing import List

from GUI_utils import Node
from json_util import JSONSerializable


class Command(JSONSerializable):
    def __init__(self, action: str = "NOP"):
        self.action = action


class LocatableCommand(Command):
    def __init__(self, action: str, node: Node):
        super().__init__(action)
        self.target = node


class InfoCommand(Command):
    def __init__(self, question: str):
        super().__init__('info')
        self.question = question


class ClickCommand(LocatableCommand):
    def __init__(self, node: Node):
        super().__init__('click', node)


class NavigateCommand(Command):
    def __init__(self, action: str):
        super().__init__(action)


class NextCommand(NavigateCommand):
    def __init__(self):
        super().__init__('next')


class PreviousCommand(NavigateCommand):
    def __init__(self):
        super().__init__('previous')


class SelectCommand(NavigateCommand):
    def __init__(self):
        super().__init__('select')


class CommandResponse(JSONSerializable):
    def __init__(self, command_type: str, state: str, duration: int, **kwargs):
        self.type = command_type
        self.state = state
        self.duration = duration

    @classmethod
    def get_kwargs_from_response(cls, response: dict) -> dict:
        if response is None:
            return {
                'command_type': 'UnknownNone',
                'state': 'UnknownNone',
                'duration': -1,
            }
        return {
            'command_type': response.get('type', 'Unknown'),
            'state': response.get('state', 'Unknown'),
            'duration': int(response.get('duration', -1)),
        }

    @classmethod
    def create_from_response(cls, response: dict):
        return cls(**cls.get_kwargs_from_response(response))


class LocatableCommandResponse(CommandResponse):
    def __init__(self, target_node: Node, acted_node: Node, locating_attempts: int = -1, **kwargs):
        super().__init__(**kwargs)
        self.target_node = target_node
        self.acted_node = acted_node
        self.locating_attempts = locating_attempts

    @classmethod
    def get_kwargs_from_response(cls, response: dict) -> dict:
        kwargs = super().get_kwargs_from_response(response)
        kwargs['target_node'] = Node.createNodeFromDict(response.get('targetWidget', {}))
        kwargs['acted_node'] = Node.createNodeFromDict(response.get('actedWidget', {}))
        kwargs['locating_attempts'] = response.get('locatingAttempts', -1)
        return kwargs


class NavigateCommandResponse(CommandResponse):
    def __init__(self, navigated_node: Node, **kwargs):
        super().__init__(**kwargs)
        self.navigated_node = navigated_node

    @classmethod
    def get_kwargs_from_response(cls, response: dict) -> dict:
        kwargs = super().get_kwargs_from_response(response)
        kwargs['navigated_node'] = Node.createNodeFromDict(response.get('navigatedWidget', {}))
        return kwargs


class InfoCommandResponse(CommandResponse):
    def __init__(self, answer: str, **kwargs):
        super().__init__(**kwargs)
        self.answer = answer

    @classmethod
    def get_kwargs_from_response(cls, response: dict) -> dict:
        kwargs = super().get_kwargs_from_response(response)
        kwargs['answer'] = Node.createNodeFromDict(response.get('result', {}))
        return kwargs