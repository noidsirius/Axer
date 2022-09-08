import json
import logging

from GUI_utils import Node
from app import App
from data_utils import RecordDataManager, ReplayDataManager
from utils import create_gif

logger = logging.getLogger(__name__)


class CreateA11yPuppetryVideoTask:
    def __init__(self, app: App):
        self.app = app

    async def execute(self):
        record_manager = RecordDataManager(app=self.app)
        images = []
        image_to_nodes = {}
        for step in record_manager.snapshot_indices:
            image_path = record_manager.recorder_screenshot_map[step]
            images.append(str(image_path))
            images.append(image_path)
            image_to_nodes[image_path.resolve()] = [record_manager.acted_nodes.get(step, Node())]
        create_gif(source_images=images,
                   target_gif=record_manager.recorder_path.joinpath("video.gif"),
                   image_to_nodes=image_to_nodes,
                   outline=(220, 20, 60),
                   duration=500)
        logger.info("Original video is created!")
        if 'touch' in ReplayDataManager.get_existing_controllers(app=self.app):
            touch_replay_manager = ReplayDataManager(app=self.app, controller_mode='touch')
            for snapshot in await touch_replay_manager.async_get_snapshots():
                logger.info(f"Creating video of TB Focusable Nodes in Snapshot {snapshot.name}")
                if not snapshot.address_book.execute_single_action_tb_focusables_path.exists():
                    continue
                image_path = snapshot.initial_screenshot.resolve()
                image_to_nodes = {image_path.resolve(): []}
                with open(snapshot.address_book.execute_single_action_tb_focusables_path) as f:
                    for line in f:
                        node = Node.createNodeFromDict(json.loads(line))
                        image_to_nodes[image_path.resolve()].append(node)
                create_gif(source_images=[image_path],
                           target_gif=snapshot.address_book.execute_single_action_tb_focusables_gif_path,
                           image_to_nodes=image_to_nodes,
                           outline=(220, 20, 60),
                           duration=500)


