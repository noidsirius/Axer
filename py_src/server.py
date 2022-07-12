#!/usr/bin/env python

import asyncio
import json
import logging
import os
from pathlib import Path

from GUI_utils import Node
from adb_utils import download_android_file
from command import ClickCommand
import websockets

logger = logging.getLogger(__name__)

proxy_users_connections = {}
recorder_connection = None
message_queue = asyncio.queues.Queue


async def register(websocket):
    global recorder_connection
    message_str = await websocket.recv()
    message = json.loads(message_str)
    if 'name' not in message:
        logger.error(f"The register message was broken! Message: '{message_str}'")
        return
    if message['name'] == 'RECORDER':
        if recorder_connection is not None:
            logger.error(f"The recorder connection exists! Message: '{message_str}'")
            return
        else:
            logger.info("A new recorder is registered!")
            recorder_connection = websocket
    elif message['name'] in proxy_users_connections:
        logger.error(f"A proxy user with the same name {message['name']} already exists! Message: '{message_str}'")
        return
    else:
        logger.info(f"A new proxy user {message['name']} is registered!")
        proxy_users_connections[message['name']] = websocket
    try:
        await websocket.wait_closed()
    finally:
        if message['name'] != 'RECORDER':
            proxy_users_connections.pop(message['name'])
        else:
            recorder_connection = None
            # TODO: need to update the proxy users the recorder connection is closed!
    logger.info(f"Connection to {message['name']} is closed!")


async def recorder_handler():
    while True:
        if recorder_connection is None:
            await asyncio.sleep(3)
            continue
        message_str = await recorder_connection.recv()
        message = json.loads(message_str)

        if 'start recording' in message and 'packageName' in message:
            logger.info(f"Recording is started with the packageName: '{message['packageName']}")

        if 'end recording' in message and 'scriptName' in message:
            logger.info(f"Recording is ended with the scriptName: {message['scriptName']}")
            # Download the script from the emulator
            dir_path = "edu.cmu.hcii.sugilite/scripts"
            dest_path = Path(__file__).resolve().with_name('dev_results').joinpath(message['scriptName'])
            if not dest_path.exists():
                os.makedirs(dest_path)
            return_code = await download_android_file(dir_path, message['scriptName']+'.txt', dest_path)

        # Converting to the ClickCommand
        text = message['Text'] if 'Text' in message else ''
        class_name = message['Class_Name'] if 'Class_Name' in message else ''
        resource_id = message['Resource_ID'] if 'Resource_ID' in message else ''
        content_desc = message['Content_Desc'] if 'Content_Desc' in message else ''
        pkg_name = message['Package_Name'] if 'Package_Name' in message else ''
        xpath = message['Xpath'] if 'Xpath' in message else ''

        node_dict = {
            'text': text,
            'class_name': class_name,
            'resource_id': resource_id,
            'content_desc': content_desc,
            'pkg_name': pkg_name,
            'xpath': xpath
        }

        node = Node.createNodeFromDict(node_dict)
        command = ClickCommand(node)

        logger.info(f"Received a message from Recorder: Message: '{message_str},"
                    f" sending to all proxy users : {','.join(proxy_users_connections.keys())}")
        # logger.info(f"Generated the click command: Command: '{command.toJSONStr()}")
        websockets.broadcast(proxy_users_connections.values(), message_str)


async def main():
    async with websockets.serve(register, "localhost", 8765):
        await recorder_handler()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())