import sys
import tarfile
import tempfile
from enum import Enum
from pathlib import Path
from typing import Union

sys.path.append("..")  # TODO: Need to refactor
from command import Command, create_command_from_dict
from json_util import JSONSerializable



class SocketMessageAction(Enum):
    NOP = 'NOP'
    REGISTER = 'REGISTER'
    START = 'START'
    SEND_COMMAND = 'SENDCOMMAND'
    END_RECORD = 'ENDRECORD'
    INTERRUPT = 'INTERRUPT'
    TERMINATE = 'TERMINATE'

    @staticmethod
    def get(name: str) -> 'SocketMessageAction':
        for action in SocketMessageAction:
            if action.value == name:
                return action
        return SocketMessageAction.NOP


def zip_directory(source_dir: Union[str, Path], output_path: Union[str, Path] = None, arcname: str = None) -> Path:
    if isinstance(source_dir, str):
        source_dir = Path(source_dir)
    if arcname is None:
        arcname = source_dir.name
    if output_path is None:
        _, output_path = tempfile.mkstemp(suffix='.tar.gz')
        output_path = Path(output_path)
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(source_dir, arcname=arcname)
    return output_path


def write_bytes_to_file(data: bytes, output_path: Union[str, Path] = None) -> Path:
    if output_path is None:
        _, output_path = tempfile.mkstemp(suffix='.tar.gz')
    output_path = Path(output_path)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path


class SocketMessage(JSONSerializable):
    def __init__(self, action: Union[SocketMessageAction, str] = SocketMessageAction.NOP, **kwargs):
        if isinstance(action, str):
            action = SocketMessageAction.get(action)
        self.action = action

    @classmethod
    def create_from_dict(cls, json_socket_message: dict):
        return cls(**json_socket_message)


class RegisterSM(SocketMessage):
    def __init__(self, name: str, **kwargs):
        super().__init__(action=SocketMessageAction.REGISTER)
        self.name = name  # TODO: Distinguish controller and name, Register multiple replayers with same controllers


class StartRecordSM(SocketMessage):
    def __init__(self, package_name: str, **kwargs):
        super().__init__(action=SocketMessageAction.START)
        self.package_name = package_name


class SendCommandSM(SocketMessage):
    def __init__(self, command: Command, index: int, **kwargs):
        super().__init__(action=SocketMessageAction.SEND_COMMAND)
        self.command = command
        self.index = index

    @classmethod
    def create_from_dict(cls, json_socket_message: dict):
        command = create_command_from_dict(json_socket_message.get('command', {}))
        return cls(command=command, index=int(json_socket_message.get('index', -1)))


class EndRecordSM(SocketMessage):
    def __init__(self, **kwargs):
        super().__init__(action=SocketMessageAction.END_RECORD)


class InterruptSM(SocketMessage):
    def __init__(self, **kwargs):
        super().__init__(action=SocketMessageAction.INTERRUPT)


class TerminateSM(SocketMessage):
    def __init__(self, **kwargs):
        super().__init__(action=SocketMessageAction.TERMINATE)


def create_socket_message_from_dict(json_socket_message: dict) -> SocketMessage:
    if 'action' not in json_socket_message:
        return SocketMessage()
    action = json_socket_message['action']
    action_to_command_map = {
        SocketMessageAction.REGISTER: RegisterSM,
        SocketMessageAction.START: StartRecordSM,
        SocketMessageAction.SEND_COMMAND: SendCommandSM,
        SocketMessageAction.END_RECORD: EndRecordSM,
        SocketMessageAction.INTERRUPT: InterruptSM,
        SocketMessageAction.TERMINATE: TerminateSM
    }
    if SocketMessageAction.get(action) in action_to_command_map:
        return action_to_command_map[SocketMessageAction.get(action)].create_from_dict(json_socket_message)
    return SocketMessage()
