#!/usr/bin/env python

import asyncio
import random

import websockets
import json

from command import InfoCommand, create_command_from_dict


async def hello():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        name = input("What's your name? (Options: ['RECORDER', 'TOCUH', 'TB', 'API']) ")
        message = {'name': name}
        await websocket.send(json.dumps(message))
        if name == 'RECORDER':
            for i in range(5):
                command = InfoCommand(question=f"Command {i}")
                await websocket.send(command.toJSONStr())
                await asyncio.sleep(1 + random.random()*3)
        else:
            while True:
                command_str = await websocket.recv()
                command_json = json.loads(command_str)
                print(f"Received command '{command_str}'")
                command = create_command_from_dict(command_json)



if __name__ == "__main__":
    asyncio.run(hello())