#!/usr/bin/env python

import asyncio
import random
import sys

import websockets
import json

from command import InfoCommand, create_command_from_dict


async def recorder_client():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        message = {'name': 'RECORDER'}
        await websocket.send(json.dumps(message))
        for i in range(5):
            command = InfoCommand(question=f"Command {i}")
            await websocket.send(command.toJSONStr())
            await asyncio.sleep(1 + random.random()*3)


async def proxy_user_client(proxy_user_name: str):
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        message = {'name': proxy_user_name}
        await websocket.send(json.dumps(message))
        while True:
            command_str = await websocket.recv()
            command_json = json.loads(command_str)
            print(f"Received command '{command_str}'")
            command = create_command_from_dict(command_json)


if __name__ == "__main__":
    name = sys.argv[1]
    if name == 'RECORDER':
        asyncio.run(recorder_client())
    else:
        asyncio.run(proxy_user_client(name))