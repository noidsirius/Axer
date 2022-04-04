import sys
from pathlib import Path
import argparse
import asyncio
import logging

from audit import TalkBackExploreAudit, OversightStaticAudit
from consts import DEVICE_NAME, ADB_HOST, ADB_PORT
from ppadb.client_async import ClientAsync as AdbClient
from results_utils import AddressBook
from logger_utils import ColoredFormatter
from snapshot import EmulatorSnapshot, DeviceSnapshot, Snapshot

logger = logging.getLogger(__name__)


async def main(args, address_book: AddressBook):
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

        if args.audit == "talkback_explore":
            logger.info("Audit: TalkBack Explore")
            await TalkBackExploreAudit(snapshot).execute()
        elif args.audit == "oversight_static":
            logger.info("Audit: Oversight Static")
            await OversightStaticAudit(snapshot).execute()

    except Exception as e:
        logger.error("Exception happened in analyzing the snapshot", exc_info=e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=str, help='Name of the snapshot on the running AVD, consider all snapshots in the app directory if not provided')
    parser.add_argument('--output-path', type=str, required=True, help='The path that outputs will be written')
    parser.add_argument('--app-name', type=str, required=True, help='Name of the app under test')
    parser.add_argument('--audit', type=str, required=True, help='Name of the audit on the app')
    parser.add_argument('--oversight', action='store_true', help='Evaluating Oversight')
    parser.add_argument('--emulator', action='store_true', help='Determines if the device is an emulator')
    parser.add_argument('--static', action='store_true', help='Do not use device')
    parser.add_argument('--initial-load', action='store_true', help='If the device is an emulator, loads the snapshot initially')
    parser.add_argument('--no-save-snapshot', action='store_true', help='If the device is an emulator, does not save any extra snapshot')
    parser.add_argument('--device', type=str, default=DEVICE_NAME, help='The device name')
    parser.add_argument('--adb-host', type=str, default=ADB_HOST, help='The host address of ADB')
    parser.add_argument('--adb-port', type=int, default=ADB_PORT, help='The port number of ADB')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    app_result_path = Path(args.output_path).joinpath(args.app_name)
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
        exit()
    for snapshot_result_path in snapshot_result_paths:
        snapshot_name = snapshot_result_path.name
        log_path_name = f"{snapshot_name}_{args.audit}.log"
        log_path = app_result_path.joinpath(log_path_name)

        if args.debug:
            level = logging.DEBUG
        else:
            level = logging.INFO

        logger_handlers = [logging.FileHandler(log_path, mode='w')]
        logger_handlers[0].setFormatter(ColoredFormatter(detailed=True, use_color=True))
        if not args.quiet:
            logger_handlers.append(logging.StreamHandler())
            logger_handlers[-1].setFormatter(ColoredFormatter(detailed=False, use_color=True))
        logging.basicConfig(handlers=logger_handlers)
        # ---------------- Start Hack -----------
        py_src_path = Path(sys.argv[0]).parent
        py_src_file_names = [p.name[:-len(".py")] for p in py_src_path.iterdir() if p.is_file() and p.name.endswith(".py")]
        for name in logging.root.manager.loggerDict:
            if name in py_src_file_names or name == "__main__":
                logging.getLogger(name).setLevel(level)
        # ----------------- End Hack ------------
        logger.info(f"Analyzing Snapshot '{snapshot_name}' in app '{args.app_name}'...")
        address_book = AddressBook(snapshot_result_path)
        asyncio.run(main(args=args, address_book=address_book))
        logger.info(f"Done Analyzing Snapshot '{snapshot_name}' in app '{args.app_name}'")
