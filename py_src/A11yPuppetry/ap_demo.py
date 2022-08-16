import argparse
import asyncio
import logging
import os
import signal
import sys


sys.path.append("..")  # TODO: Need to refactor
from A11yPuppetry.recorder import recorder_client

from adb_utils import launch_specified_application, install_application
from A11yPuppetry.replayer import proxy_user_client
from shell_utils import run_bash
from datetime import datetime
from pathlib import Path
from typing import List, Union

from consts import DEVICE_NAME, WS_IP, WS_PORT, ADB_HOST, ADB_PORT
from genymotion_utils import list_instances, stop_instances, setup_ap_instance
from logger_utils import initialize_logger
from utils import synch_run

logger = logging.getLogger(__name__)

INTERRUPT_SIGNAL = False


def signal_handler(sig, frame):
    global INTERRUPT_SIGNAL
    logger.info('You pressed Ctrl+C! Please wait...')
    INTERRUPT_SIGNAL = True


async def main(result_path: Union[str, Path], controllers: List[str], ws_ip: str, ws_port: int,
               usecase_path: Union[str, Path] = None):
    if usecase_path is not None and isinstance(usecase_path, str):
        usecase_path = Path(usecase_path)
    online_replay = usecase_path is None
    setup_tasks = []

    app_paths = [f"$LATTE_PATH/Setup/latte.apk"]
    for controller_mode in controllers:
        setup_tasks.append(asyncio.create_task(setup_ap_instance(instance_name=controller_mode,
                                                                 app_paths=app_paths)))
    if online_replay:
        setup_tasks.append(asyncio.create_task(setup_ap_instance(instance_name="RECORDER",
                                                                 app_paths=app_paths)))
    logger.info(f"Setting up {len(setup_tasks)} new instances...")
    setup_results = await asyncio.gather(*setup_tasks)
    if not all(r for r in setup_results):
        logger.error(f"Some instances could not be created! Terminating")
        await stop_instances()
        return
    if INTERRUPT_SIGNAL:
        await stop_instances()
        return
    replayer_instances = await list_instances()
    replayer_tasks = []
    single_usecase = not online_replay
    for inst in replayer_instances:
        if inst.name != 'RECORDER':
            task = asyncio.create_task(proxy_user_client(inst.name, inst.get_adb_device_name(),
                                                         result_path=result_path,
                                                         ws_ip=ws_ip,
                                                         ws_port=ws_port,
                                                         single_usecase=single_usecase))
            replayer_tasks.append(task)
    if online_replay:
        recorder_instance = None
        for inst in replayer_instances:
            if inst.name == "RECORDER":
                recorder_instance = inst
                break
        if recorder_instance is None:
            logger.error(
                f"There is no recorder instance in online mode! Instances {[inst.name for inst in replayer_instances]}")
        else:
            replayer_instances.remove(recorder_instance)
            logger.info("Installing recorder...")
            if await install_application(apk_path="$LATTE_PATH/Setup/Sugilite.apk", device_name=recorder_instance.get_adb_device_name()):
                await run_bash(f"adb -s {recorder_instance.get_adb_device_name()} "
                               f"shell settings put secure enabled_accessibility_services "
                               f"edu.cmu.hcii.sugilite/edu.cmu.hcii.sugilite.accessibility_service.SugiliteAccessibilityService")
                await launch_specified_application("edu.cmu.hcii.sugilite", device_name=recorder_instance.get_adb_device_name())
                for i in range(180):  # TODO: the total duration of the demo is at most 30 minutes
                    if INTERRUPT_SIGNAL:
                        break
                    logger.info("Waiting...")
                    await asyncio.sleep(10)
            else:
                logger.error(
                    f"Problem with install recorder! Terminating")
    else:
        package_name = usecase_path.parent.name
        logger.info(f"Starting offline recording for package {package_name} from usecase in {usecase_path}")
        recorder_task = asyncio.create_task(recorder_client(recorder_path=usecase_path,
                                                            package_name=package_name,
                                                            ws_ip=ws_ip,
                                                            ws_port=ws_port))
        for i in range(180):  # TODO: the total duration of the demo is at most 30 minutes
            if INTERRUPT_SIGNAL:
                break
            if recorder_task.done() and all(t.done() for t in replayer_tasks):
                break
            logger.info("Waiting...")
            await asyncio.sleep(10)


    logger.info("Stopping all instances")
    await stop_instances()

    logger.info("Stopping Replayers tasks")
    for task in replayer_tasks:
        task.cancel()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-path', type=str, required=True, help='The path that outputs will be written')
    parser.add_argument('--controllers', nargs='+', default=[], required=True,
                        help='List of the controllers that replay the usecase')
    parser.add_argument('--ws-ip', type=str, default=WS_IP, help='The ip address of WebSocket Server')
    parser.add_argument('--ws-port', type=int, default=WS_PORT, help='The port number of WebSocket Server')
    parser.add_argument('--adb-host', type=str, default=ADB_HOST, help='The host address of ADB')
    parser.add_argument('--adb-port', type=int, default=ADB_PORT, help='The port number of ADB')
    parser.add_argument('--usecase-path', type=str, default=None, help='The path to usecase for offline replay')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()

    result_path = Path(args.output_path)
    current_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = result_path.joinpath(f'DEMO_{current_time_str}.log')  # TODO: Not a good place for logs
    initialize_logger(log_path=log_path, quiet=args.quiet, debug=args.debug)
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    synch_run(main(result_path=result_path, controllers=args.controllers, ws_ip=args.ws_ip, ws_port=args.ws_port,
                   usecase_path=args.usecase_path))
