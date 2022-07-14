import sys
sys.path.append("..")  # TODO: Need to refactor
import argparse
import asyncio
import json
import os
import shutil
import logging
from pathlib import Path

import websockets
from ppadb.client_async import ClientAsync as AdbClient

from adb_utils import launch_specified_application, run_bash
from consts import ADB_HOST, ADB_PORT, WS_IP, WS_PORT, DEVICE_NAME
from controller import create_controller
from logger_utils import initialize_logger
from results_utils import AddressBook
from snapshot import DeviceSnapshot
from socket_utils import RegisterSM, StartRecordSM, SendCommandSM, EndRecordSM, create_socket_message_from_dict
from task.execute_single_action_task import ExecuteSingleActionTask

logger = logging.getLogger(__name__)

pkg_name_to_apk_path = {
    'com.colpit.diamondcoming.isavemoney': '/Users/navid/StudioProjects/Latte/BM_APKs/ase_apks/com.colpit.diamondcoming.isavemoney.apk'
}


async def proxy_user_client(controller_mode: str,
                            device_name: str,
                            app_path: Path,
                            ws_ip: str = WS_IP,
                            ws_port: int = WS_PORT):
    uri = f"ws://{ws_ip}:{ws_port}"
    client = AdbClient(host=ADB_HOST, port=ADB_PORT)
    device = await client.device(device_name)
    controller = create_controller(controller_mode, device_name=device.serial)
    logger.info(f"Controller is {controller.name()}")
    async with websockets.connect(uri) as websocket:
        await websocket.send(RegisterSM(name=controller_mode).toJSONStr())
        message_str = await websocket.recv()
        message = create_socket_message_from_dict(json.loads(message_str))
        if not isinstance(message, StartRecordSM):
            logger.error(f"Waiting for StartRecordSM, Unexpected message: '{message_str}'")
            return
        logger.info(f"The replaying for package {message.package_name} is started!")
        # Reinstall the application, then start it
        if message.package_name not in pkg_name_to_apk_path:
            logger.error(f"The package name {message.package_name} is unknown!")
            return
        await run_bash(f"adb -s {device_name} uninstall {message.package_name}")
        ret_value, _, _ = await run_bash(f"adb -s {device_name} install -r -g {pkg_name_to_apk_path[message.package_name]}")
        if ret_value != 0:
            logger.error(f"The APK {pkg_name_to_apk_path[message.package_name]} could not be installed!")
            return
        await launch_specified_application(pkg_name=message.package_name, device_name=device_name)
        await asyncio.sleep(3)
        # Replaying the commands from server
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-path', type=str, required=True, help='The path that outputs will be written')
    parser.add_argument('--app-name', type=str, required=True, help='Name of the app under test')
    parser.add_argument('--controller', type=str, required=True, help='Name of the controller that replays the usecase')
    parser.add_argument('--emulator', action='store_true', help='Determines if the device is an emulator')
    parser.add_argument('--device', type=str, default=DEVICE_NAME, help='The device name')
    parser.add_argument('--ws-ip', type=str, default=WS_IP, help='The ip address of WebSocket Server')
    parser.add_argument('--ws-port', type=int, default=WS_PORT, help='The port number of WebSocket Server')
    parser.add_argument('--adb-host', type=str, default=ADB_HOST, help='The host address of ADB')
    parser.add_argument('--adb-port', type=int, default=ADB_PORT, help='The port number of ADB')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()

    app_result_path = Path(args.output_path).joinpath(args.app_name)
    if app_result_path.exists():
        shutil.rmtree(app_result_path)
    app_result_path.mkdir()
    log_path = app_result_path.joinpath(f'replay_{args.controller}.log')
    initialize_logger(log_path=log_path, quiet=args.quiet, debug=args.debug)
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(proxy_user_client(args.controller, args.device, app_path=app_result_path,
                                  ws_ip=args.ws_ip, ws_port=args.ws_port))
