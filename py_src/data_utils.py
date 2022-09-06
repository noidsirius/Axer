import json
import shutil
from collections import defaultdict
from typing import List, Union
from cachetools import cached, TTLCache

from GUI_utils import Node
from app import App
from command import Command, create_command_response_from_dict, create_command_from_dict, LocatableCommandResponse, \
    LocatableCommand
from consts import BLIND_MONKEY_EVENTS_TAG
from snapshot import Snapshot


class RecordDataManager:
    def __init__(self, app: App):
        self.app = app
        self.recorder_path = self.app.app_path.joinpath("RECORDER")

        if not self.recorder_path.is_dir():
            raise "The recorder directory does not exists"
        self.user_review_path = self.recorder_path.joinpath("user_review.jsonl")
        if not self.user_review_path.exists():
            self.user_review_path.touch()
        usecase_path = self.recorder_path.joinpath("usecase.jsonl")
        self.commands = {}
        self.snapshot_indices = []
        self.recorder_bounds_map = {}
        if usecase_path.exists():
            with open(app.app_path.joinpath("RECORDER").joinpath("usecase.jsonl")) as f:
                for i, line in enumerate(f):
                    self.commands[i] = create_command_from_dict(json.loads(line))
                    self.snapshot_indices.append(i)
                    if isinstance(self.commands[i], LocatableCommand):
                        screen_bounds = [0, 0, 1080, 2220]  # TODO: Move to consts
                        self.recorder_bounds_map[i] = str(list(self.commands[i].target.get_normalized_bounds(screen_bounds)))
                    else:
                        self.recorder_bounds_map[i] = "[0.0,0.0,0.0,0.0]"
        self.snapshot_indices.append("END")
        self.recorder_screenshot_map = {}
        self.recorder_layout_map = {}
        for index in self.snapshot_indices:
            self.recorder_screenshot_map[index] = self.recorder_path.joinpath(f"S_{index}.png")
            self.recorder_layout_map[index] = self.recorder_path.joinpath(f"S_{index}.xml")

    def get_user_review(self, step: str) -> Union[str, None]:
        with open(self.user_review_path) as f:
            for line in f:
                user_review = json.loads(line)
                if user_review['step'] == str(step):
                    return user_review['content']
        return None

    def write_user_review(self, step: str, content: str):
        step = str(step)
        user_review = {'step': step, 'content': content}
        existing_user_review_content = self.get_user_review(step)
        if existing_user_review_content is None:
            with open(self.user_review_path, "a") as f:
                f.write(json.dumps(user_review) + "\n")
        else:
            # TODO: This is a terrible way of updating the file, needs to be refactored
            existing_user_review_str = json.dumps({'step': step, 'content': existing_user_review_content})
            with open(self.user_review_path) as f:
                all_file = f.read()
            all_file = all_file.replace(existing_user_review_str, json.dumps(user_review))
            with open(self.user_review_path, "w") as f:
                f.write(all_file)



class ReplayDataManager:
    def __init__(self, app: App, controller_mode: str, recreate: bool = False):
        self.app = app
        self.controller_mode = controller_mode
        self.replay_path = app.app_path.joinpath(f"REPLAY_{controller_mode}")
        if self.replay_path.exists() and recreate:
            shutil.rmtree(self.replay_path)
        self.replay_path.mkdir(parents=True, exist_ok=True)
        self.replay_usecase_report_path = self.replay_path.joinpath("usecase_report.jsonl")
        self.replay_usecase_report_path.touch()
        self.replay_usecase_finish_path = self.replay_path.joinpath("finish.txt")
        self.snapshots = []

    @staticmethod
    def get_existing_controllers(app: App) -> List[str]:
        controllers = []
        for subdir in app.app_path.iterdir():
            if subdir.is_dir() and subdir.name.startswith("REPLAY_"):
                controllers.append(subdir.name[len("REPLAY_"):])
        return controllers

    def add_new_action(self, snapshot: Snapshot):
        self.snapshots.append(snapshot)
        snapshot_info = {
            'index': len(self.snapshots),
            'snapshot_name': snapshot.name
        }
        with open(self.replay_usecase_report_path, "a") as f:
            f.write(f"{json.dumps(snapshot_info)}\n")

    def finish(self, last_snapshot: Snapshot):
        with open(self.replay_usecase_finish_path, "w") as f:
            f.write(f"{json.dumps({'snapshot_name': last_snapshot.name})}\n")

    def get_snapshots(self) -> List[Snapshot]:
        self.app.update_snapshots()
        snapshots = []
        with open(self.replay_usecase_report_path) as f:
            for line in f:
                snapshot_info = json.loads(line)
                snapshots.append(self.app.get_snapshot(snapshot_info['snapshot_name']))
        return snapshots

    @cached(cache=TTLCache(maxsize=1024, ttl=10))
    def get_problematic_steps(self) -> dict:
        problems = defaultdict(list)
        for snapshot in self.get_snapshots():
            snapshot_index = snapshot.name.split("_")[-1]

            step_info = self.get_step_info(snapshot_index)
            if step_info['response'].state != 'COMPLETED':
                reason = 'Unknown'
                reason = step_info['response'].state
                problems[snapshot_index].append(reason)
        return problems

    @cached(cache=TTLCache(maxsize=1024, ttl=10))
    def get_step_info(self, index: str) -> dict:
        snapshot = self.app.get_snapshot(name=f"{self.controller_mode}.S_{index}")
        step_info = {
            'controller': self.controller_mode,
            'command': Command(),
            'response': create_command_response_from_dict(command=Command(), result={}),
        }

        if snapshot is None:
            return step_info
        if index != 'END':
            if not snapshot.address_book.execute_single_action_results_path.exists():
                return step_info
            with open(snapshot.address_book.execute_single_action_results_path) as f:
                step_info_json = json.load(f)

            step_info['command'] = create_command_from_dict(step_info_json.get('command', {}))
            response = step_info['response'] = create_command_response_from_dict(step_info['command'],
                                                                  step_info_json.get('response', {}))
            if len(snapshot.nodes) > 0 and snapshot.nodes[0].bounds[0] != 0:
                screen_bounds = snapshot.nodes[0].bounds  # TODO: Not correct when the keyboard is enabled
            else:
                screen_bounds = [0, 0, 1080, 2220]  # TODO: Move to consts
            if isinstance(response, LocatableCommandResponse):
                step_info['bounds'] = str(list(response.acted_node.get_normalized_bounds(screen_bounds)))
            else:
                step_info['bounds'] = "[0.0,0.0,0.0,0.0]"
            step_info['atf_issues'] = []
            if snapshot.address_book.execute_single_action_atf_issues_path.exists():
                with open(snapshot.address_book.execute_single_action_atf_issues_path) as f:
                    for line in f:
                        node = Node.createNodeFromDict(json.loads(line))
                        step_info['atf_issues'].append(str(list(node.get_normalized_bounds(screen_bounds))))

            step_info['logs'] = snapshot.address_book.get_log_path(mode=self.controller_mode, index=0)
            step_info['event_logs'] = snapshot.address_book.get_log_path(mode=self.controller_mode, index=0,
                                                                     extension=BLIND_MONKEY_EVENTS_TAG)

        step_info['layout'] = snapshot.address_book.get_layout_path(mode=self.controller_mode, index=0)
        if self.controller_mode == 'tb_dir' and snapshot.address_book.tb_explore_visited_nodes_gif.exists():
            step_info['screenshot'] = snapshot.address_book.tb_explore_visited_nodes_gif
        else:
            step_info['screenshot'] = snapshot.initial_screenshot

        return step_info


