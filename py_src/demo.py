import argparse
import asyncio
import logging
import json
from ppadb.client_async import ClientAsync as AdbClient
from padb_utils import ParallelADBLogger, save_screenshot
from latte_utils import talkback_tree_nodes, latte_capture_layout
from GUI_utils import get_actions_from_layout
from utils import annotate_elements

logger = logging.getLogger(__name__)


async def execute_latte_command(command: str, extra: str):
    client = AdbClient(host="127.0.0.1", port=5037)
    device = await client.device("emulator-5554")
    padb_logger = ParallelADBLogger(device)
    if command == "tb_a11y_tree":
        windows_info, bm_logs = await talkback_tree_nodes(padb_logger, verbose=True)
        logger.info(f"Windows Info: {json.dumps(windows_info, indent=4)}")
        logger.info(f"Latte Logs: {bm_logs}")
    if command == "capture_layout":
        log, layout = await padb_logger.execute_async_with_log(latte_capture_layout())
        logger.info(layout)
    if command == "get_actions":  # The extra is the output path
        await save_screenshot(device, extra)
        log, layout = await padb_logger.execute_async_with_log(latte_capture_layout())
        if "Problem with XML" in layout:
            logger.error(layout)
            logger.error("Logs: " + log)
            return
        actions = get_actions_from_layout(layout)
        annotate_elements(extra, extra, actions, outline=(255, 0, 255), width=15, scale=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--command', type=str, help='The command sending to Latte')
    parser.add_argument('--extra', type=str, default="", help='The extra information sent to Latte')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    if args.command:
        asyncio.run(execute_latte_command(args.command, args.extra))
