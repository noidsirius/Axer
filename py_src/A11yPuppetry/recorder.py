import sys
sys.path.append("..")  # TODO: Need to refactor
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from random import random
from typing import Union

import websockets

from A11yPuppetry.socket_utils import RegisterSM, StartRecordSM, SendCommandSM, EndRecordSM
from consts import WS_IP, WS_PORT

logger = logging.getLogger(__name__)


async def recorder_client(usecase_path: Union[str, Path], package_name: str, ws_ip: str = WS_IP,
                          ws_port: int = WS_PORT):
    uri = f"ws://{ws_ip}:{ws_port}"
    async with websockets.connect(uri) as websocket:
        logger.info("Registering...")
        await websocket.send(RegisterSM(name='RECORDER').toJSONStr())
        await asyncio.sleep(2)
        logger.info("Start recording...")
        await websocket.send(StartRecordSM(package_name=package_name).toJSONStr())
        await asyncio.sleep(5)
        with open(usecase_path) as f:
            for line in f:
                d = json.loads(line)
                await websocket.send(SendCommandSM(command=d).toJSONStr())
                await asyncio.sleep(1 + random()*3)  # TODO: A more elegant solution for simulating delay between steps
        logger.info("End recording...")
        await websocket.send(EndRecordSM().toJSONStr())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--usecase-path', type=str, required=True, help='The path to the usecase that will'
                                                                        ' be transmitted to the replayers')
    parser.add_argument('--package-name', type=str, required=True, help='Package name of the app')
    parser.add_argument('--ws-ip', type=str, default=WS_IP, help='The ip address of WebSocket Server')
    parser.add_argument('--ws-port', type=int, default=WS_PORT, help='The port number of WebSocket Server')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(recorder_client(usecase_path=args.usecase_path,
                                package_name=args.package_name,
                                ws_ip=args.ws_ip,
                                ws_port=args.ws_port))
