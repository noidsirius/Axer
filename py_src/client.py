#!/usr/bin/env python

import asyncio
import random
import sys
from pathlib import Path

from ppadb.client_async import ClientAsync as AdbClient

import websockets
import json

from command import InfoCommand, create_command_from_dict
from consts import ADB_HOST, ADB_PORT
from controller import create_controller
from results_utils import AddressBook
from snapshot import DeviceSnapshot
from task.execute_single_action_task import ExecuteSingleActionTask


async def recorder_client():
    # uri = "ws://137.184.188.248:8765"
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        message = {'name': 'RECORDER'}
        await websocket.send(json.dumps(message))
        with open("../dev_results/iSaveMoney/usecase.jsonl") as f:
            for line in f:
                d = json.loads(line)
                message = {'socket_command': 'EXECUTE', 'command': d}
                await websocket.send(json.dumps(message))
                await asyncio.sleep(0.1 + random.random()*3)
        message = {'socket_command': 'TERMINATE'}
        await websocket.send(json.dumps(message))


async def proxy_user_client(proxy_user_name: str, device_name: str, controller_mode: str):
    uri = "ws://localhost:8765"
    client = AdbClient(host=ADB_HOST, port=ADB_PORT)
    device = await client.device(device_name)
    controller = create_controller(controller_mode, device_name=device.serial)
    print(f"Controller is {controller.name()}")
    result_path = Path("../dev_results")
    app_path = result_path.joinpath("my_app")
    async with websockets.connect(uri) as websocket:
        message = {'name': proxy_user_name}
        await websocket.send(json.dumps(message))
        i = 0
        while True:
            i += 1
            command_str = await websocket.recv()
            command_json = json.loads(command_str)
            if command_json.get("socket_command", "TERMINATE") == 'TERMINATE':
                break
            command = create_command_from_dict(command_json.get('command', {}))
            print(f"Received command {command.name()}: '{command_str}'")
            address_book = AddressBook(snapshot_result_path=app_path.joinpath(f"M_{i}"))
            snapshot = DeviceSnapshot(address_book=address_book, device=device)
            await snapshot.setup(first_setup=True)
            await ExecuteSingleActionTask(snapshot, controller=controller, command=command).execute()



if __name__ == "__main__":
    name = sys.argv[1]
    if name == 'RECORDER':
        asyncio.run(recorder_client())
    else:
        device_name = sys.argv[2]
        controller_mode = name
        asyncio.run(proxy_user_client(name, device_name, controller_mode))