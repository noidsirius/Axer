import json
from pathlib import Path
import argparse
import asyncio
import logging

from GUI_utils import Node
from app import App
from command import create_command_from_dict
from consts import DEVICE_NAME, ADB_HOST, ADB_PORT
from ppadb.client_async import ClientAsync as AdbClient

from controller import create_controller
from results_utils import AddressBook
from logger_utils import ColoredFormatter, initialize_logger
from snapshot import EmulatorSnapshot, DeviceSnapshot, Snapshot
from task.app_task import TakeSnapshotTask, StoatSaveSnapshotTask
from task.create_a11y_puppetry_video import CreateA11yPuppetryVideoTask
from task.create_action_gif_task import CreateActionGifTask
from task.execute_single_action_task import ExecuteSingleActionTask
from task.execute_usecase_task import ExecuteUsecaseTask
from task.extract_actions_task import ExtractActionsTask
from task.oversight_static_task import OversightStaticTask
from task.perform_actions_task import PerformActionsTask
from task.process_screenshot_task import ProcessScreenshotTask
from task.record_usecase_task import RecordUsecaseTask
from task.snapshot_task import RemoveSummaryTask
from task.talkback_explore_task import TalkBackExploreTask
from utils import synch_run

logger = logging.getLogger(__name__)


async def execute_snapshot_task(args, address_book: AddressBook):
    try:
        if not args.static:
            client = AdbClient(host=args.adb_host, port=args.adb_port)
            device = await client.device(args.device)
            if args.emulator:
                snapshot = EmulatorSnapshot(address_book=address_book,
                                            device=device,
                                            no_save_snapshot=args.no_save_snapshot)
                await snapshot.setup(first_setup=True, initial_emulator_load=args.initial_load)
            else:
                snapshot = DeviceSnapshot(address_book=address_book, device=device)
                await snapshot.setup(first_setup=True)
        else:
            snapshot = Snapshot(address_book=address_book)
            await snapshot.setup()

        if args.snapshot_task == "talkback_explore":
            logger.info("Snapshot Task: TalkBack Explore")
            target_node = None
            if args.extra is not None:
                target_node = Node.createNodeFromDict(json.loads(args.extra))
            await TalkBackExploreTask(snapshot, target_node=target_node).execute()
        elif args.snapshot_task == "extract_actions":
            logger.info("Snapshot Task: Extract Actions")
            await ExtractActionsTask(snapshot).execute()
        elif args.snapshot_task == "remove_summary":
            logger.info("Snapshot Task: Remove Summary")
            await RemoveSummaryTask(snapshot).execute()
        elif args.snapshot_task == "perform_actions":
            logger.info("Snapshot Task: Perform Actions")
            await PerformActionsTask(snapshot).execute()
        elif args.snapshot_task == "create_action_gif":
            logger.info("Snapshot Task: Create Action Gif")
            await CreateActionGifTask(snapshot).execute()
        elif args.snapshot_task == "oversight_static":
            logger.info("Snapshot Task: Oversight Static")
            await OversightStaticTask(snapshot).execute()
        elif args.snapshot_task == "process_screenshot":
            logger.info("Snapshot Task: Process Screenshot")
            await ProcessScreenshotTask(snapshot).execute()
    except Exception as e:
        logger.error("Exception happened in analyzing the snapshot", exc_info=e)


async def execute_app_task(args, app_path: Path):
    try:
        if args.static:
            logger.error("Not supported")
            return

        try:
            client = AdbClient(host=args.adb_host, port=args.adb_port)
            device = await client.device(args.device)
        except Exception as e:
            logger.error(f"Exception happend in connecting to the device, Exception: {e}")
            device = None

        if args.app_task == "take_snapshot":
            logger.info("App Task: Take a snapshot")
            await TakeSnapshotTask(app_path=app_path, device=device).execute()
        elif args.app_task == "execute_single_action":
            logger.info("App Task: Execute Single Action")
            app = App(app_name=app_path.name, result_path=app_path.parent)
            snapshot = await app.take_snapshot(device=device, snapshot_name="TMP_1")
            info = json.loads(args.extra)
            controller_mode = info['controller']
            controller = create_controller(mode=controller_mode, device=device)
            command = create_command_from_dict(info['command'])
            await ExecuteSingleActionTask(snapshot, device=device, controller=controller, command=command).execute()
        elif args.app_task == "stoat_save_snapshot":
            logger.info("App Task: Save an Emulator Snapshot")
            if not args.emulator or args.no_save_snapshot:
                logger.error("The device should be an emulator")
                return
            await StoatSaveSnapshotTask(app_path=app_path, device=device).execute()

        elif args.app_task == "ap_video":
            logger.info("App Task: Create A11yPuppetry Video")
            app = App(app_name=app_path.name, result_path=app_path.parent)
            await CreateA11yPuppetryVideoTask(app=app).execute()

        elif args.app_task == "record_usecase":
            logger.info("App Task: Record a use case")
            await RecordUsecaseTask(app_path=app_path, device=device).execute()
        elif args.app_task == "execute_usecase":
            logger.info("App Task: Execute a use case")
            await ExecuteUsecaseTask(app_path=app_path, device=device).execute()
        else:
            logger.error("Nothing is matched!")

    except Exception as e:
        logger.error("Exception happened in analyzing the snapshot", exc_info=e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=str, help='Name of the snapshot on the running AVD, consider all snapshots in the app directory if not provided')
    parser.add_argument('--output-path', type=str, required=True, help='The path that outputs will be written')
    parser.add_argument('--app-name', type=str, required=True, help='Name of the app under test')
    parser.add_argument('--app-task', type=str, required=False, help='Name of the task on the app')
    parser.add_argument('--snapshot-task', type=str, required=False, help='Name of the task on the snapshot')
    parser.add_argument('--oversight', action='store_true', help='Evaluating Oversight')
    parser.add_argument('--emulator', action='store_true', help='Determines if the device is an emulator')
    parser.add_argument('--windows', action='store_true', help='Determines if the host operating system is windows')
    parser.add_argument('--static', action='store_true', help='Do not use device')
    parser.add_argument('--initial-load', action='store_true', help='If the device is an emulator, loads the snapshot initially')
    parser.add_argument('--no-save-snapshot', action='store_true', help='If the device is an emulator, does not save any extra snapshot')
    parser.add_argument('--device', type=str, default=DEVICE_NAME, help='The device name')
    parser.add_argument('--extra', type=str, default=None, help='Extra information for tasks')
    parser.add_argument('--adb-host', type=str, default=ADB_HOST, help='The host address of ADB')
    parser.add_argument('--adb-port', type=int, default=ADB_PORT, help='The port number of ADB')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    app_result_path = Path(args.output_path).joinpath(args.app_name)
    if args.windows:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if args.snapshot_task is not None:
        snapshot_result_paths = []
        if args.snapshot:
            snapshot_result_paths = [app_result_path.joinpath(args.snapshot)]
            if not snapshot_result_paths[0].exists():
                snapshot_result_paths[0].mkdir(parents=True)
        else:
            for snapshot_result_path in app_result_path.iterdir():
                if snapshot_result_path.is_dir():
                    snapshot_result_paths.append(snapshot_result_path)

        if len(snapshot_result_paths) == 0:
            print("No snapshot is selected!")
            exit(1)
        for snapshot_result_path in snapshot_result_paths:
            snapshot_name = snapshot_result_path.name
            log_path_name = f"{snapshot_name}_{args.snapshot_task}.log"
            log_path = app_result_path.joinpath(log_path_name)

            initialize_logger(log_path=log_path, quiet=args.quiet, debug=args.debug)
            logger.info(f"Executing {args.snapshot_task} for Snapshot '{snapshot_name}' in app '{args.app_name}'...")
            address_book = AddressBook(snapshot_result_path)
            synch_run(execute_snapshot_task(args=args, address_book=address_book))
            logger.info(f"Done executing {args.snapshot_task} for Snapshot '{snapshot_name}' in app '{args.app_name}'")
    elif args.app_task is not None:
        if not app_result_path.exists() or not app_result_path.is_dir():
            app_result_path.mkdir(parents=True)
        log_path = app_result_path.joinpath(f"app_{args.app_task}.log")
        initialize_logger(log_path=log_path, quiet=args.quiet, debug=args.debug)
        logger.info(f"Executing {args.app_task} for app '{args.app_name}'...")
        synch_run(execute_app_task(args=args, app_path=app_result_path))
        logger.info(f"Done executing {args.app_task}  in app '{args.app_name}'")
    else:
        print("Either app_task or snapshot_task should be provided!")
        exit(1)
