import sys
from datetime import datetime

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
from data_utils import ReplayDataManager
from app import App
from utils import synch_run
from shell_utils import run_bash
from adb_utils import launch_specified_application
from consts import ADB_HOST, ADB_PORT, WS_IP, WS_PORT, DEVICE_NAME
from controller import create_controller
from logger_utils import initialize_logger
from socket_utils import RegisterSM, StartRecordSM, SendCommandSM, EndRecordSM, create_socket_message_from_dict, \
    zip_directory, TerminateSM, InterruptSM
from task.execute_single_action_task import ExecuteSingleActionTask

logger = logging.getLogger(__name__)

# TODO: Need to be moved to a config file
pkg_name_to_apk_path = {
    'com.colpit.diamondcoming.isavemoney': '/Users/navid/StudioProjects/Latte/BM_APKs/ase_apks/com.colpit.diamondcoming.isavemoney.apk',
    'com.dictionary': '/Users/navid/StudioProjects/Latte/BM_APKs/ase_apks/com.dictionary.apk',
    'com.yelp.android': '/Users/navid/StudioProjects/Latte/BM_APKs/ase_apks/com.yelp.android.apk',
    'com.offerup': '/Users/navid/StudioProjects/Latte/BM_APKs/ase_apks/com.offerup.apk',
    'com.different.toonme': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.different.toonme.apk', # Didn't work
    'com.zhiliaoapp.musically': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.zhiliaoapp.musically.apk',
    'com.squareup.cash': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.squareup.cash.apk',
    'com.instagram.android': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.instagram.android.apk',
    'com.whatsapp': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.whatsapp.apk', # Didn't work, Time Settings
    'com.amazon.mShop.android.shopping': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.amazon.mShop.android.shopping.apk',
    'com.engro.cleanerforsns': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.engro.cleanerforsns.apk', # Has lots of ads
    'com.bingo.cooler.phonecleaner': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.bingo.cooler.phonecleaner.apk', # Has lots of ads
    'com.facebook.orca': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.facebook.orca.apk',
    'com.mcdonalds.app': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.mcdonalds.app.apk', # Problem with the second step
    'com.snapchat.android': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.snapchat.android.apk',
    'com.booking': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.booking.apk',
    'com.netflix.mediaclient': '/Users/navid/StudioProjects/Latte/BM_APKs/topplay_apks/com.netflix.mediaclient.apk', # Didn't work

}


async def proxy_user_client(controller_mode: str,
                            device_name: str,
                            result_path: Path,
                            ws_ip: str = WS_IP,
                            ws_port: int = WS_PORT,
                            single_usecase: bool = False):
    uri = f"ws://{ws_ip}:{ws_port}"
    client = AdbClient(host=ADB_HOST, port=ADB_PORT)
    device = await client.device(device_name)
    controller = create_controller(controller_mode, device_name=device.serial)
    enabled_assistive_services = ["tb"] if "tb_" in controller_mode else None  # TODO: More elegant
    logger.info(f"Controller is {controller.name()}")
    async with websockets.connect(uri, max_size=1_000_000_000) as websocket:  # TODO: Add to constants
        await websocket.send(RegisterSM(name=controller_mode).toJSONStr())
        while True:
            message_str = await websocket.recv()
            message = create_socket_message_from_dict(json.loads(message_str))
            if isinstance(message, TerminateSM):
                logger.info(f"Terminating the proxy user!")
                return
            if isinstance(message, InterruptSM):
                logger.info(f"Interrupt message received but no recording was going on.")
                continue
            if not isinstance(message, StartRecordSM):
                logger.error(f"Waiting for StartRecordSM, Unexpected message: '{message_str}'")
                return
            logger.info(f"The replaying for package {message.package_name} is started!")
            app = App(app_name=message.package_name, result_path=result_path)
            rd_manager = ReplayDataManager(app=app, controller_mode=controller_mode)
            # Reset the application or Reinstall it, then start it
            package_name = app.package_name
            if package_name not in pkg_name_to_apk_path:
                logger.error(f"The package name {package_name} is unknown!")
                return
            ret_value, stdout, stderr = await run_bash(f"adb -s {device_name} shell pm clear {package_name}")
            if ret_value != 0:
                logger.error(f"The package {package_name} could not be cleared! STDOUT: {stdout}, STD:ERR: {stderr}")
                await run_bash(f"adb -s {device_name} uninstall {package_name}")
            # Reinstalling to grant all permissions
            ret_value, stdout, stderr = await run_bash(f"adb -s {device_name} install -r -g {pkg_name_to_apk_path[package_name]}")
            if ret_value != 0:
                logger.debug(f"Installing logs:\n\tOUT: '{stdout}'\n\tErr: '{stderr}'")
                logger.error(f"The APK {pkg_name_to_apk_path[package_name]} could not be installed!")
                return
            await launch_specified_application(pkg_name=package_name, device_name=device_name)
            logger.info(f"App {package_name} is started!")
            if "localhost" not in device_name and package_name == "com.colpit.diamondcoming.isavemoney":
                await asyncio.sleep(60)
            else:
                await asyncio.sleep(10)
            logger.info(f"Listening for commands!")
            # Replaying the commands from server
            i = 0
            while True:
                i += 1
                message_str = await websocket.recv()
                message = create_socket_message_from_dict(json.loads(message_str))

                if isinstance(message, SendCommandSM):
                    command = message.command
                    index = message.index
                    logger.info(f"Received command({index}) {command.name()}: '{message_str}'")
                    snapshot = await app.take_snapshot(device=device,
                                                       snapshot_name=f"{controller_mode}.S_{index}",
                                                       enabled_assistive_services=enabled_assistive_services)
                    await ExecuteSingleActionTask(snapshot=snapshot, device=device, controller=controller, command=command).execute()
                    rd_manager.add_new_action(snapshot=snapshot)
                elif isinstance(message, EndRecordSM):
                    logger.info(f"The replay is finished!")
                    snapshot = await app.take_snapshot(device=device,
                                                       snapshot_name=f"{controller_mode}.S_END",
                                                       enabled_assistive_services=enabled_assistive_services)
                    rd_manager.finish(snapshot)
                    tar_file_path = zip_directory(source_dir=app.app_path)
                    logger.info(f"The report is zipped in {tar_file_path}")
                    with open(tar_file_path, "rb") as f:
                        await websocket.send(f.read())
                    logger.info(f"The report has been sent to the server, removing zip file!")
                    try:
                        tar_file_path.unlink()
                    except OSError as e:
                        logger.error("Error in removing file: %s : %s" % (tar_file_path, e.strerror))
                    break
                elif isinstance(message, InterruptSM):
                    logger.info(f"Interrupt message received!")
                    snapshot = await app.take_snapshot(device=device,
                                                       snapshot_name=f"{controller_mode}.S_END",
                                                       enabled_assistive_services=enabled_assistive_services)
                    rd_manager.finish(snapshot)
                    break
                else:
                    logger.error(f"Unexpected terminating the proxy user! message: '{message_str}'")
                    return

            if single_usecase:
                break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-path', type=str, required=True, help='The path that outputs will be written')
    parser.add_argument('--controller', type=str, required=True, help='Name of the controller that replays the usecase')
    parser.add_argument('--emulator', action='store_true', help='Determines if the device is an emulator')
    parser.add_argument('--device', type=str, default=DEVICE_NAME, help='The device name')
    parser.add_argument('--ws-ip', type=str, default=WS_IP, help='The ip address of WebSocket Server')
    parser.add_argument('--ws-port', type=int, default=WS_PORT, help='The port number of WebSocket Server')
    parser.add_argument('--adb-host', type=str, default=ADB_HOST, help='The host address of ADB')
    parser.add_argument('--adb-port', type=int, default=ADB_PORT, help='The port number of ADB')
    parser.add_argument('--single-usecase', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()

    result_path = Path(args.output_path)
    current_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = result_path.joinpath(f'REPLAY_{args.controller}_{current_time_str}.log')  # TODO: Not a good place for logs
    initialize_logger(log_path=log_path, quiet=args.quiet, debug=args.debug)
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    synch_run(proxy_user_client(args.controller, args.device,
                                result_path=result_path,
                                ws_ip=args.ws_ip,
                                ws_port=args.ws_port,
                                single_usecase=args.single_usecase))
