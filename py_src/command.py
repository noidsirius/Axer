import json
from typing import List

from GUI_utils import Node


class Command:
    def __init__(self, action: str = "NOP"):
        self.action = action

    def toJSONStr(self, excluded_attributes: List[str] = None) -> str:
        if excluded_attributes is None:
            excluded_attributes = []

        def get_items(o) -> dict:
            res = {}
            for (k, v) in o.__dict__.items():
                if k in excluded_attributes:
                    continue
                if isinstance(v, Node):
                    v = v.toJSON()
                res[k] = v
            return res

        return json.dumps(self,
                          default=get_items,
                          sort_keys=True)

    def toJSON(self, excluded_attributes: List[str] = None) -> dict:
        return json.loads(self.toJSONStr(excluded_attributes))


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
