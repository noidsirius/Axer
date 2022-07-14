from command import Command, create_command_from_dict
from json_util import JSONSerializable


class SocketMessage(JSONSerializable):
    def __init__(self, action: str = "NOP", **kwargs):
        self.action = action

    @classmethod
    def create_from_dict(cls, json_socket_message: dict):
        return cls(**json_socket_message)


class RegisterSM(SocketMessage):
    def __init__(self, name: str, **kwargs):
        super().__init__(action='REGISTER')
        self.name = name


class StartRecordSM(SocketMessage):
    def __init__(self, package_name: str, **kwargs):
        super().__init__(action='START')
        self.package_name = package_name


class SendCommandSM(SocketMessage):
    def __init__(self, command: Command, **kwargs):
        super().__init__(action='SENDCOMMAND')
        self.command = command

    @classmethod
    def create_from_dict(cls, json_socket_message: dict):
        command = create_command_from_dict(json_socket_message.get('command', {}))
        return cls(command=command)


class EndRecordSM(SocketMessage):
    def __init__(self, **kwargs):
        super().__init__(action='ENDRECORD')


def create_socket_message_from_dict(json_socket_message: dict) -> SocketMessage:
    if 'action' not in json_socket_message:
        return SocketMessage()
    action = json_socket_message['action']
    action_to_command_map = {
        'REGISTER': RegisterSM,
        'START': StartRecordSM,
        'SENDCOMMAND': SendCommandSM,
        'ENDRECORD': EndRecordSM
    }
    if action in action_to_command_map:
        return action_to_command_map[action].create_from_dict(json_socket_message)
    return SocketMessage()
