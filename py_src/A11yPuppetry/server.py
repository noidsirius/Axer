import argparse
import sys
sys.path.append("..")  # TODO: Need to refactor
import asyncio
import json
import logging
import os
from enum import Enum
import websockets

from consts import WS_IP, WS_PORT
from socket_utils import create_socket_message_from_dict, RegisterSM, StartRecordSM, SendCommandSM, EndRecordSM

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


async def server_main_loop():
    global server_state
    logger.info("In Server Main Loop!")
    while server_running:
        if server_state == ServerState.CLEANING_UP:
            if recorder_connection is None and len(proxy_users_connections) == 0:
                server_state = ServerState.REGISTERING
            else:
                await asyncio.sleep(5)
                continue
        if server_state == ServerState.REGISTERING:
            await asyncio.sleep(3)
            continue
        assert recorder_connection is not None
        logger.info("Waiting for message from the recorder...")
        message_str = await recorder_connection.recv()
        try:
            socket_message = create_socket_message_from_dict(json.loads(message_str))
        except Exception as e:
            logger.error(f"The received message was not in JSON format, message: '{message_str}'")
            continue
        if server_state == ServerState.WAITING_TO_START:
            if not isinstance(socket_message, StartRecordSM):
                logger.error(f"The server is in state {ServerState.WAITING_TO_START} "
                             f"expecting to receive a StartRecordSM, Message: {message_str}")
                break  # TODO: It can be more flexible than breaking the process

            package_name = socket_message.package_name
            logger.info(f"The recording is started for package {package_name}!")
            server_state = ServerState.RECORDING
        elif server_state == ServerState.RECORDING:
            if isinstance(socket_message, SendCommandSM):
                command = socket_message.command
                logger.info(f"The next command is '{command}'")
            elif isinstance(socket_message, EndRecordSM):
                logger.info(f"The recording is finished!")
                server_state = ServerState.CLEANING_UP
            else:
                logger.error(f"The server is in state {ServerState.RECORDING} "
                             f"expecting to receive a SendCommandSM, Message: {message_str}")
                break  # TODO: It can be more flexible than breaking the process
        else:
            logger.error(f"The server is in a wrong state {server_state}!, Message: {message_str}")
            break  # TODO: It can be more flexible than breaking the process

        logger.info(f"Broadcasting the message to proxy users: {','.join(proxy_users_connections.keys())}")
        websockets.broadcast(proxy_users_connections.values(), message_str)

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


async def main(ws_ip: str = WS_IP, ws_port: str = WS_PORT):
    async with websockets.serve(register_handler, ws_ip, ws_port):
        await server_main_loop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--ws-ip', type=str, default=WS_IP, help='The ip address of WebSocket Server')
    parser.add_argument('--ws-port', type=int, default=WS_PORT, help='The port number of WebSocket Server')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main(args.ws_ip, args.ws_port))
