import json
import logging

from GUI_utils import Node
from command import ClickCommand, CommandResponse, LocatableCommandResponse
from consts import BLIND_MONKEY_TAG, BLIND_MONKEY_EVENTS_TAG
from controller import TalkBackTouchController, TouchController, A11yAPIController, TalkBackAPIController
from latte_executor_utils import report_atf_issues
from padb_utils import ParallelADBLogger
from results_utils import AddressBook, Actionables, capture_current_state, ActionResult
from snapshot import EmulatorSnapshot, Snapshot
from task.snapshot_task import SnapshotTask
from utils import annotate_elements, annotate_rectangle, create_gif

logger = logging.getLogger(__name__)


class CreateActionGifTask(SnapshotTask):
    def __init__(self, snapshot: Snapshot):
        super().__init__(snapshot)

    async def execute(self):
        if not self.snapshot.address_book.audit_path_map[AddressBook.PERFORM_ACTIONS].exists():
            logger.error("The actions should be performed first!")
            return
        whelper = self.snapshot.address_book.whelper
        for action_result in whelper.get_actions():
            summary = whelper.action_summary(action_result.index)
            tb_nodes = []
            with open(self.snapshot.address_book.tb_explore_visited_nodes_path) as f:
                for line in f.readlines():
                    node = Node.createNodeFromDict(json.loads(line.strip()))
                    if node.xpath == action_result.node.xpath:
                        break
                    tb_nodes.append(node)
            if summary['tb_dir_issue']:
                tb_screenshots = [str(self.snapshot.initial_screenshot), self.snapshot.initial_screenshot, self.snapshot.address_book.snapshot_result_path.parent.parent.parent.joinpath("404.png")]
            else:
                tb_nodes.append(action_result.node)
                tb_screenshots = [str(self.snapshot.initial_screenshot), self.snapshot.initial_screenshot, self.snapshot.address_book.get_screenshot_path("tb_touch", action_result.index), self.snapshot.address_book.get_screenshot_path("tb_touch", action_result.index)]
            tb_screenshots_to_nodes = {
                tb_screenshots[1].resolve(): tb_nodes
            }
            create_gif(source_images=tb_screenshots,
                       target_gif=self.snapshot.address_book.get_gif_path("tb_touch", action_result.index),
                       image_to_nodes=tb_screenshots_to_nodes,
                       duration=500)

            touch_screenshots = [str(self.snapshot.initial_screenshot), self.snapshot.initial_screenshot, self.snapshot.address_book.get_screenshot_path("touch", action_result.index), self.snapshot.address_book.get_screenshot_path("touch", action_result.index)]
            touch_screenshots_to_nodes = {
                touch_screenshots[1].resolve(): [action_result.node]
            }
            create_gif(source_images=touch_screenshots,
                       target_gif=self.snapshot.address_book.get_gif_path("touch", action_result.index),
                       image_to_nodes=touch_screenshots_to_nodes,
                       duration=500)



