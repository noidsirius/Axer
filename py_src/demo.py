import argparse
import asyncio
import logging
import json
from ppadb.client_async import ClientAsync as AdbClient
from padb_utils import ParallelADBLogger
from latte_utils import talkback_tree_nodes


logger = logging.getLogger(__name__)


async def execute_latte_command(command: str):
    client = AdbClient(host="127.0.0.1", port=5037)
    device = await client.device("emulator-5554")
    padb_logger = ParallelADBLogger(device)
    if command == "nav_tree":
        windows_info, bm_logs = await talkback_tree_nodes(padb_logger, verbose=False)
        logger.info(f"Windows Info: {json.dumps(windows_info, indent=4, sort_keys=True)}")
        logger.info(f"Latte Logs: {bm_logs}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--command', type=str, help='The command sending to Latte')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    if args.command:
        asyncio.run(execute_latte_command(args.command))

