import argparse
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Union
sys.path.append("..")  # TODO: Need to refactor
import asyncio
import json
import logging
import os
from enum import Enum
import websockets

from consts import WS_IP, WS_PORT
from utils import synch_run
from logger_utils import initialize_logger
from socket_utils import create_socket_message_from_dict, RegisterSM, StartRecordSM, SendCommandSM, EndRecordSM, \
    write_bytes_to_file, InterruptSM

logger = logging.getLogger(__name__)

proxy_users_connections = {}
recorder_connection: websockets.WebSocketClientProtocol = None
message_queue = asyncio.queues.Queue


class ServerState(Enum):  # The state of the Server
    REGISTERING = 1
    WAITING_TO_START = 2
    RECORDING = 3
    CLEANING_UP = 4


server_state = ServerState.REGISTERING
server_running = True


async def register_handler(websocket: websockets.WebSocketClientProtocol):
    global recorder_connection, server_state
    message_str = await websocket.recv()
    socket_message = create_socket_message_from_dict(json.loads(message_str))
    if not isinstance(socket_message, RegisterSM):
        logger.error(f"The receive message was not a RegisterSM! Message: '{message_str}'")
        return
    if socket_message.name == 'RECORDER':
        if recorder_connection is not None:
            assert server_state != ServerState.REGISTERING
            logger.error(f"The recorder connection exists! Message: '{message_str}'")
            return
        else:
            assert server_state == ServerState.REGISTERING
            logger.info("A new recorder is registered!")
            recorder_connection = websocket
            server_state = ServerState.WAITING_TO_START
    elif server_state not in [ServerState.REGISTERING, ServerState.WAITING_TO_START]:
        logger.error(f"The recording process is already started! Message: '{message_str}'")
        return
    elif socket_message.name in proxy_users_connections:
        logger.error(f"A proxy user with the same name {socket_message.name} already exists! Message: '{message_str}'")
        return
    else:
        logger.info(f"A new proxy user {socket_message.name} is registered!")
        proxy_users_connections[socket_message.name] = websocket

    try:
        await websocket.wait_closed()
    finally:
        if socket_message.name != 'RECORDER':
            proxy_users_connections.pop(socket_message.name)
        else:
            recorder_connection = None
            # TODO: need to update the proxy users the recorder connection is closed!
    logger.info(f"Connection to {socket_message.name} is closed!")


async def download_report(websocket: websockets.WebSocketClientProtocol,
                          output_directory: Path,
                          client_name: str = "UNKNOWN"):
    data = await websocket.recv()
    tar_file_path = write_bytes_to_file(data=data)
    with tarfile.open(tar_file_path, "r:*") as tar:
        tar.extractall(output_directory)
    logger.info(f"The report of {client_name} has been added to {output_directory}")
    try:
        tar_file_path.unlink()
    except OSError as e:
        logger.error("Error in removing file: %s : %s" % (tar_file_path, e.strerror))


async def server_main_loop(result_path: Union[str, Path]):
    global server_state
    global recorder_connection
    if isinstance(result_path, str):
        result_path = Path(result_path)
    logger.info("In Server Main Loop!")
    server_result_path = None
    download_tasks = []
    command_index = 0
    while server_running:
        if server_state == ServerState.CLEANING_UP:
            command_index = 0
            if len(download_tasks) > 0:
                await asyncio.wait(download_tasks)
                download_tasks = []
                logger.info("All download report tasks are finished!")
            if recorder_connection is None:
                server_state = ServerState.REGISTERING
                server_result_path = None
                logger.info("Waiting for the Recorder..")
            else:
                await asyncio.sleep(5)
                continue
        if server_state == ServerState.REGISTERING:
            command_index = 0
            await asyncio.sleep(3)
            continue
        assert recorder_connection is not None
        logger.info("Waiting for message from the recorder...")
        try:
            message_str = await recorder_connection.recv()
        except Exception as e:
            logger.error(f"Exception happens for receiving message from the recoder, Exception: {e}")
            websockets.broadcast(proxy_users_connections.values(), InterruptSM().toJSONStr())
            if recorder_connection is not None and not recorder_connection.closed:
                try:
                    await recorder_connection.close()
                except Exception as e:
                    logger.error(f"Failed to close RECORDER connection, Exception: '{e}'")
            recorder_connection = None
            server_state = ServerState.REGISTERING
            continue
        logger.debug(f"Received message: '{message_str}'")
        try:
            socket_message = create_socket_message_from_dict(json.loads(message_str))
        except Exception as e:
            logger.error(f"The received message was not in JSON format, message: '{message_str}', Exception: {e}")
            continue
        if server_result_path and server_result_path.is_dir():
            with open(server_result_path.joinpath("messages.json"), "a") as f:
                f.write(message_str+"\n")
        if server_state == ServerState.WAITING_TO_START:
            if not isinstance(socket_message, StartRecordSM):
                logger.error(f"The server is in state {ServerState.WAITING_TO_START} "
                             f"expecting to receive a StartRecordSM, Message: {message_str}")
                break  # TODO: It can be more flexible than breaking the process

            package_name = socket_message.package_name
            logger.info(f"The recording is started for package {package_name}!")
            server_result_path = result_path.joinpath(package_name).joinpath("SERVER")
            server_result_path.mkdir(parents=True, exist_ok=True)
            server_state = ServerState.RECORDING
        elif server_state == ServerState.RECORDING:
            if isinstance(socket_message, SendCommandSM):
                command = socket_message.command
                if socket_message.index == -1:  # TODO: Needs to be addressed in Sugilite
                    socket_message.index = command_index
                    message_str = socket_message.toJSONStr()
                command_index += 1
                logger.info(f"The next command is '{command}'")
            elif isinstance(socket_message, EndRecordSM):
                logger.info(f"The recording is finished!")
                server_state = ServerState.CLEANING_UP
                download_tasks.append(asyncio.create_task(download_report(websocket=recorder_connection,
                                                                          output_directory=result_path,
                                                                          client_name='RECORDER')))
            else:
                logger.error(f"The server is in state {ServerState.RECORDING} "
                             f"expecting to receive a SendCommandSM, Message: {message_str}")
                break  # TODO: It can be more flexible than breaking the process
        else:
            logger.error(f"The server is in a wrong state {server_state}!, Message: {message_str}")
            break  # TODO: It can be more flexible than breaking the process

        logger.info(f"Broadcasting the message to proxy users: {','.join(proxy_users_connections.keys())}")
        websockets.broadcast(proxy_users_connections.values(), message_str)
        if server_state == ServerState.CLEANING_UP:
            # Once the recording is finished, server waits for all replayers to upload their reports
            # to the server. The report is a tar.gz file of the directory of the app in replayers' machines
            for name, connection in proxy_users_connections.items():
                download_tasks.append(asyncio.create_task(download_report(websocket=connection,
                                                                          output_directory=result_path,
                                                                          client_name=name)))

    proxy_connection_items = list(proxy_users_connections.items())
    for name, proxy_users_connection in proxy_connection_items:
        if not proxy_users_connection.closed:
            try:
                await proxy_users_connection.close()
            except Exception as e:
                logger.error(f"Failed to close connection of {name}, Exception: '{e}'")
    if recorder_connection is not None and not recorder_connection.closed:
        try:
            await recorder_connection.close()
        except Exception as e:
            logger.error(f"Failed to close RECORDER connection, Exception: '{e}'")


async def main(result_path: Union[str, Path], ws_ip: str = WS_IP, ws_port: str = WS_PORT):
    async with websockets.serve(register_handler, ws_ip, ws_port, max_size=1_000_000_000):  # TODO: Add to constants
        await server_main_loop(result_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-path', type=str, required=True, help='The path that outputs will be written')
    parser.add_argument('--ws-ip', type=str, default=WS_IP, help='The ip address of WebSocket Server')
    parser.add_argument('--ws-port', type=int, default=WS_PORT, help='The port number of WebSocket Server')
    args = parser.parse_args()
    result_path = Path(args.output_path)
    current_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = result_path.joinpath(f'SERVER_{current_time_str}.log')  #  TODO: Not a good place for logs
    initialize_logger(log_path=log_path)
    logging.basicConfig(level=logging.INFO)
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    synch_run(main(result_path, args.ws_ip, args.ws_port))
