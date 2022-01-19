from pathlib import Path
import argparse
import asyncio
import logging
from snapshot import Snapshot, AddressBook

logger = logging.getLogger(__name__)


def bm_explore(snapshot_result_path: Path, snapshot_name: str):
    address_book = AddressBook(snapshot_result_path)
    snapshot = Snapshot(snapshot_name, address_book)
    success_explore = asyncio.run(snapshot.explore())
    if not success_explore:
        logger.error("Problem with explore!")
        return
    asyncio.run(snapshot.validate_by_stb())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=str, required=True, help='Name of the snapshot on the running AVD')
    parser.add_argument('--output-path', type=str, required=True, help='The path that outputs will be written')
    parser.add_argument('--app-name', type=str, required=True, help='Name of the app under test')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()

    app_result_path = Path(args.output_path).joinpath(args.app_name)
    snapshot_result_path = app_result_path.joinpath(args.snapshot)
    if not snapshot_result_path.exists():
        snapshot_result_path.mkdir(parents=True)
    log_path = app_result_path.joinpath(f"{args.snapshot}.log")

    if args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    if args.quiet:
        logging.basicConfig(filename=log_path,
                            filemode='w',
                            level=level)
    else:
        logging.basicConfig(level=level,
                            handlers=[
                                logging.FileHandler(log_path, mode='w'),
                                logging.StreamHandler()])
    logger.info(f"Analyzing Snapshot '{args.snapshot}' in app '{args.app_name}'...")
    bm_explore(snapshot_result_path, args.snapshot)
