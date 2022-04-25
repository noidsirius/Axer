import json
import logging

from GUI_utils import Node
from snapshot import Snapshot
from task.snapshot_task import SnapshotTask
from utils import annotate_elements

logger = logging.getLogger(__name__)


def is_node_clickable(node: Node, use_naf: bool = True) -> bool:
    return node.clickable or \
           "16" in node.a11y_actions or \
           (node.naf if use_naf else False)


class ExtractActionsTask(SnapshotTask):
    def __init__(self, snapshot: Snapshot):
        super().__init__(snapshot)

    async def execute(self):
        self.snapshot.address_book.initiate_extract_actions_task()
        only_visible: bool = True
        no_ad: bool = True
        actionable_node_queries = [is_node_clickable]
        if only_visible:
            actionable_node_queries.append(lambda node: node.visible)
        if no_ad:
            actionable_node_queries.append(lambda node: not node.is_ad)

        actionable_nodes = self.snapshot.get_nodes(filter_query=lambda node: all(q(node) for q in actionable_node_queries))
        visited_resource_ids = set()
        unique_resource_actionable_nodes = []
        na11y_actionable_nodes = []
        for node in actionable_nodes:
            if not node.important_for_accessibility:
                na11y_actionable_nodes.append(node)
            if node.resource_id:
                if node.resource_id in visited_resource_ids:
                    continue
                visited_resource_ids.add(node.resource_id)
            unique_resource_actionable_nodes.append(node)
        tb_reachable_actionable_nodes = []
        if self.snapshot.address_book.tb_explore_visited_nodes_path.exists():
            with open(self.snapshot.address_book.tb_explore_visited_nodes_path) as f:
                for line in f.readlines():
                    tb_reachable_node = Node.createNodeFromDict(json.loads(line))
                    if self.is_xpath_actionable(tb_reachable_node.xpath):
                        node = self.snapshot.xpath_to_node[tb_reachable_node.xpath]
                        if no_ad and node.is_ad:
                            continue
                        tb_reachable_actionable_nodes.append(node)

        with open(self.snapshot.address_book.extract_actions_all_actionable_nodes_path, "w") as f:
            for node in actionable_nodes:
                f.write(f"{node.toJSONStr()}\n")
        with open(self.snapshot.address_book.extract_actions_unique_resource_actionable_nodes_path, "w") as f:
            for node in unique_resource_actionable_nodes:
                f.write(f"{node.toJSONStr()}\n")
        with open(self.snapshot.address_book.extract_actions_not_important_a11y_actionable_nodes_path, "w") as f:
            for node in na11y_actionable_nodes:
                f.write(f"{node.toJSONStr()}\n")
        with open(self.snapshot.address_book.extract_actions_tb_reachable_actionable_nodes_path, "w") as f:
            for node in tb_reachable_actionable_nodes:
                f.write(f"{node.toJSONStr()}\n")

        annotate_elements(self.snapshot.initial_screenshot,
                          self.snapshot.address_book.extract_actions_all_actionable_nodes_screenshot,
                          actionable_nodes)
        annotate_elements(self.snapshot.initial_screenshot,
                          self.snapshot.address_book.extract_actions_unique_resource_actionable_nodes_screenshot,
                          unique_resource_actionable_nodes)
        annotate_elements(self.snapshot.initial_screenshot,
                          self.snapshot.address_book.extract_actions_not_important_a11y_actionable_nodes_screenshot,
                          na11y_actionable_nodes)
        annotate_elements(self.snapshot.initial_screenshot,
                          self.snapshot.address_book.extract_actions_tb_reachable_actionable_nodes_screenshot,
                          tb_reachable_actionable_nodes)

    def is_xpath_actionable(self, xpath: str) -> bool:

        while len(xpath) > 1 and xpath[0] == '/':
            if xpath not in self.snapshot.xpath_to_node:
                logger.error(f"The element could not be found in layout! Xpath: {xpath}")
                return False
            node = self.snapshot.xpath_to_node[xpath]
            if is_node_clickable(node):
                # TODO: Maybe we need more checks here
                return True
            xpath = xpath[:xpath.rfind("/")]
        return False


