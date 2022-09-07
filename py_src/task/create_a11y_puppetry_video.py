import logging

from GUI_utils import Node
from app import App
from data_utils import RecordDataManager
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
                   outline= (220, 20, 60),
                   duration=500)


