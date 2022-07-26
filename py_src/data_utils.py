import json
import shutil
from typing import List

from app import App
from command import Command, create_command_response_from_dict, create_command_from_dict, LocatableCommandResponse
from consts import BLIND_MONKEY_EVENTS_TAG
from snapshot import Snapshot


class ReplayDataManager:
    def __init__(self, app: App, controller_mode: str):
        self.app = app
        self.controller_mode = controller_mode
        self.replay_path = app.app_path.joinpath(f"REPLAY_{controller_mode}")
        if self.replay_path.exists():
            shutil.rmtree(self.replay_path)
        self.replay_path.mkdir(parents=True, exist_ok=False)
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
            if isinstance(response, LocatableCommandResponse):
                screen_bounds = snapshot.nodes[0].bounds  # TODO: Not correct when the keyboard is enabled
                if screen_bounds[0] != 0:
                    screen_bounds = [0, 0, 1080, 2340]  # TODO: Move to consts
                step_info['bounds'] = str(list(response.acted_node.get_normalized_bounds(screen_bounds)))
            else:
                step_info['bounds'] = "[0.0,0.0,0.0,0.0]"
            step_info['logs'] = snapshot.address_book.get_log_path(mode=self.controller_mode, index=0)
            step_info['event_logs'] = snapshot.address_book.get_log_path(mode=self.controller_mode, index=0,
                                                                     extension=BLIND_MONKEY_EVENTS_TAG)

        step_info['layout'] = snapshot.address_book.get_layout_path(mode=self.controller_mode, index=0)
        if self.controller_mode == 'tb_dir' and snapshot.address_book.tb_explore_visited_nodes_gif.exists():
            step_info['screenshot'] = snapshot.address_book.tb_explore_visited_nodes_gif
        else:
            step_info['screenshot'] = snapshot.initial_screenshot

        return step_info


