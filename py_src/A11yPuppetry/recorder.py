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

from utils import synch_run
from A11yPuppetry.socket_utils import RegisterSM, StartRecordSM, SendCommandSM, EndRecordSM, zip_directory
from consts import WS_IP, WS_PORT

logger = logging.getLogger(__name__)


async def recorder_client(recorder_path: Union[str, Path], package_name: str, ws_ip: str = WS_IP,
                          ws_port: int = WS_PORT):
    if isinstance(recorder_path, str):
        recorder_path = Path(recorder_path)
    if recorder_path.name != 'RECORDER':
        logger.error("The recorder path directory's name should be 'RECORDER'")
        return
    uri = f"ws://{ws_ip}:{ws_port}"
    async with websockets.connect(uri) as websocket:
        logger.info("Registering...")
        await websocket.send(RegisterSM(name='RECORDER').toJSONStr())
        await asyncio.sleep(2)
        logger.info("Start recording...")
        await websocket.send(StartRecordSM(package_name=package_name).toJSONStr())
        await asyncio.sleep(5)
        usecase_path = recorder_path.joinpath("usecase.jsonl")
        with open(usecase_path) as f:
            for index, line in enumerate(f):
                d = json.loads(line)
                await websocket.send(SendCommandSM(command=d, index=index).toJSONStr())
                await asyncio.sleep(1 + random()*3)  # TODO: A more elegant solution for simulating delay between steps
        logger.info("End recording...")
        await websocket.send(EndRecordSM().toJSONStr())
        tar_file_path = zip_directory(source_dir=recorder_path,
                                      arcname=f"{package_name}/{recorder_path.name}")
        logger.info(f"The recorder directory is zipped in {tar_file_path}")
        with open(tar_file_path, "rb") as f:
            await websocket.send(f.read())
        logger.info(f"The report has been sent to the server, removing zip file!")
        try:
            tar_file_path.unlink()
        except OSError as e:
            logger.error("Error in removing file: %s : %s" % (tar_file_path, e.strerror))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--recorder-path', type=str, required=True, help='The path to the prerecorded directory')
    # TODO: Add data to RECORDER directory in address_book
    parser.add_argument('--package-name', type=str, required=True, help='Package name of the app')
    parser.add_argument('--ws-ip', type=str, default=WS_IP, help='The ip address of WebSocket Server')
    parser.add_argument('--ws-port', type=int, default=WS_PORT, help='The port number of WebSocket Server')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    synch_run(recorder_client(recorder_path=args.recorder_path,
                                package_name=args.package_name,
                                ws_ip=args.ws_ip,
                                ws_port=args.ws_port))
