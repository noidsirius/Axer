import logging
from collections import defaultdict

from GUI_utils import Node
from command import NextCommand, PreviousCommand, NavigateCommandResponse, InfoCommand, InfoCommandResponse
from consts import BLIND_MONKEY_TAG, EXPLORE_VISIT_LIMIT
from controller import TalkBackDirectionalController
from json_util import unsafe_json_load
from padb_utils import ParallelADBLogger
from snapshot import EmulatorSnapshot, DeviceSnapshot, Snapshot
from utils import annotate_elements

logger = logging.getLogger(__name__)


class Auditor:
    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot

    async def talkback_explore(self):
        if not isinstance(self.snapshot, DeviceSnapshot):
            logger.error("TalkBack exploration requires a DeviceSnapshot!")
            return False
        controller = TalkBackDirectionalController()
        await controller.setup()
        padb_logger = ParallelADBLogger(self.snapshot.device)
        is_next = True
        all_nodes = {node.xpath: node for node in self.snapshot.get_nodes()}
        visited_node_xpaths_counter = defaultdict(int)
        self.snapshot.address_book.initiate_audit_talkback_explore()
        annotate_elements(self.snapshot.initial_screenshot,
                          self.snapshot.address_book.tb_explore_all_nodes_screenshot,
                          list(all_nodes.values()))
        visited_nodes = []
        none_node_count = 0
        android_logs = ""
        # --------------- Add the currently focused node to the visited nodes -----------------
        log_message_map, info_response = await padb_logger.execute_async_with_log(
            controller.execute(InfoCommand(question="a11y_focused")),
            tags=[BLIND_MONKEY_TAG])
        android_logs += f"--------- First Focused Node -----------\n" \
                        f"{log_message_map[BLIND_MONKEY_TAG]}\n" \
                        f"----------------------------------------\n"
        if info_response is not None and isinstance(info_response, InfoCommandResponse):
            node_dict = unsafe_json_load(info_response.answer)
            if node_dict is not None:
                focused_node = Node.createNodeFromDict(node_dict)
                if len(focused_node.xpath) > 0:
                    visited_nodes.append(focused_node)
                    visited_node_xpaths_counter[focused_node.xpath] += 1
        # -------------------------------------------------------------------------------------

        while True:
            command = NextCommand() if is_next else PreviousCommand()
            log_message_map, navigate_response = await padb_logger.execute_async_with_log(
                controller.execute(command),
                tags=[BLIND_MONKEY_TAG])
            android_logs += f"--------------- Navigate ---------------\n" \
                            f"{log_message_map[BLIND_MONKEY_TAG]}\n" \
                            f"----------------------------------------\n"
            if navigate_response is None or not isinstance(navigate_response, NavigateCommandResponse):
                logger.error("Terminate the exploration: Problem with navigation")
                break
            node = navigate_response.navigated_node
            if node is None or len(node.xpath) == 0:
                none_node_count += 1
                logger.warning(f"The visited node is None or does not have an xpath, none_node_count={none_node_count}."
                               f"\n\tNode: {node}")
                if none_node_count > 3:
                    logger.error(f"Terminate the exploration: none_node_count={none_node_count}")
                    break
            visited_nodes.append(node)
            visited_node_xpaths_counter[node.xpath] += 1
            logger.debug(f"Node {node.xpath} is visited {visited_node_xpaths_counter[node.xpath]} times!")
            if visited_node_xpaths_counter[node.xpath] > EXPLORE_VISIT_LIMIT:
                if is_next:
                    logger.info("Change navigation direction!")
                    android_logs += f"----------- Change Direction -----------\n"
                    is_next = False
                    for k in visited_node_xpaths_counter:
                        visited_node_xpaths_counter[k] = max(0, visited_node_xpaths_counter[k] - 1)
                    if isinstance(self.snapshot, EmulatorSnapshot):
                        await self.snapshot.reload()
                        await controller.setup()
                    continue
                logger.info(
                    f"Terminate the exploration: "
                    f"The XPath {node.xpath} is visited more than {EXPLORE_VISIT_LIMIT} times.")
                break
            # TODO: another stopping criteria: if all leaves have been visited!
        # --------------- Write essential results -----------------
        with open(self.snapshot.address_book.tb_explore_visited_nodes_path, "w") as f:
            for node in visited_nodes:
                f.write(f"{node.toJSONStr()}\n")
        with open(self.snapshot.address_book.tb_explore_android_log, "w") as f:
            f.write(android_logs)
        # --------------- Post process -----------------------
        unique_visited_nodes = []
        for xpath in visited_node_xpaths_counter:
            if xpath in all_nodes:
                unique_visited_nodes.append(all_nodes[xpath])
        annotate_elements(self.snapshot.initial_screenshot,
                          self.snapshot.address_book.tb_explore_visited_nodes_screenshot,
                          unique_visited_nodes)
        annotate_elements(self.snapshot.initial_screenshot,
                          self.snapshot.address_book.tb_explore_visited_nodes_gif,
                          visited_nodes)
        logger.info("The Talkback Exploration audit is finished!")

