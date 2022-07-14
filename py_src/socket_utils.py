from command import Command, create_command_from_dict
from json_util import JSONSerializable


class SocketMessage(JSONSerializable):
    def __init__(self, action: str = "NOP"):
        self.action = action

    @classmethod
    def create_from_dict(cls, json_command: dict):
        return cls(**json_command)


class RegisterSM(SocketMessage):
    def __init__(self, name: str):
        super().__init__(action='REGISTER')
        self.name = name


class StartRecordSM(SocketMessage):
    def __init__(self, package_name: str):
        super().__init__(action='START')
        self.package_name = package_name


class SendCommandSM(SocketMessage):
    def __init__(self, command: Command):
        super().__init__(action='SENDCOMMAND')
        self.command = command

    @classmethod
    def create_from_dict(cls, json_command: dict):
        command = create_command_from_dict(json_command.get('command', {}))
        return cls(command=command)


class EndRecordSM(SocketMessage):
    def __init__(self):
        super().__init__(action='ENDRECORD')


def create_socket_message_from_dict(json_command: dict) -> SocketMessage:
    if 'action' not in json_command:
        return SocketMessage()
    action = json_command['action']
    action_to_command_map = {
        'REGISTER': RegisterSM,
        'START': StartRecordSM,
        'SENDCOMMAND': SendCommandSM,
        'ENDRECORD': EndRecordSM
    }
    if action in action_to_command_map:
        return action_to_command_map[action].create_from_dict(json_command)
    return SocketMessage()
