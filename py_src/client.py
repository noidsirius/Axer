#!/usr/bin/env python

import asyncio
import json
import random
import sys
import logging
from pathlib import Path

import websockets
from ppadb.client_async import ClientAsync as AdbClient

from adb_utils import launch_specified_application
from command import create_command_from_dict
from consts import ADB_HOST, ADB_PORT
from controller import create_controller
from results_utils import AddressBook
from snapshot import DeviceSnapshot
from socket_utils import RegisterSM, StartRecordSM, SendCommandSM, EndRecordSM, create_socket_message_from_dict
from task.execute_single_action_task import ExecuteSingleActionTask

logger = logging.getLogger(__name__)


async def recorder_client():
    # uri = "ws://137.184.188.248:8765"
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        logger.info("Registering...")
        await websocket.send(RegisterSM(name='RECORDER').toJSONStr())
        await asyncio.sleep(5)
        logger.info("Start recording...")
        await websocket.send(StartRecordSM(package_name='com.colpit.diamondcoming.isavemoney').toJSONStr())
        await asyncio.sleep(5)
        with open("../dev_results/iSaveMoney/usecase.jsonl") as f:
            for line in f:
                d = json.loads(line)
                await websocket.send(SendCommandSM(command=d).toJSONStr())
                await asyncio.sleep(0.1 + random.random()*3)
        logger.info("End recording...")
        await websocket.send(EndRecordSM().toJSONStr())


async def proxy_user_client(proxy_user_name: str, device_name: str, controller_mode: str):
    uri = "ws://localhost:8765"
    client = AdbClient(host=ADB_HOST, port=ADB_PORT)
    device = await client.device(device_name)
    controller = create_controller(controller_mode, device_name=device.serial)
    logger.info(f"Controller is {controller.name()}")
    result_path = Path("../dev_results")
    app_path = result_path.joinpath("my_app")
    async with websockets.connect(uri) as websocket:
        await websocket.send(RegisterSM(name=proxy_user_name).toJSONStr())
        message_str = await websocket.recv()
        message = create_socket_message_from_dict(json.loads(message_str))
        if not isinstance(message, StartRecordSM):
            logger.error(f"Waiting for StartRecordSM, Unexpected message: '{message_str}'")
            return
        logger.info(f"The replaying for package {message.package_name} is started!")
        await launch_specified_application(pkg_name=message.package_name, device_name=device_name)
        await asyncio.sleep(3)
        i = 0
        while True:
            i += 1
            message_str = await websocket.recv()
            message = create_socket_message_from_dict(json.loads(message_str))
            if isinstance(message, SendCommandSM):
                command = message.command
                logger.info(f"Received command {command.name()}: '{message_str}'")
                address_book = AddressBook(snapshot_result_path=app_path.joinpath(f"M_{i}"))
                snapshot = DeviceSnapshot(address_book=address_book, device=device)
                await snapshot.setup(first_setup=True)
                await ExecuteSingleActionTask(snapshot, controller=controller, command=command).execute()
            elif isinstance(message, EndRecordSM):
                logger.info(f"The replaying is finished!")
                break


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    name = sys.argv[1]
    if name == 'RECORDER':
        asyncio.run(recorder_client())
    else:
        device_name = sys.argv[2]
        controller_mode = name
        asyncio.run(proxy_user_client(name, device_name, controller_mode))