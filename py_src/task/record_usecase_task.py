import asyncio
import json
import os
import re
from GUI_utils import Node
from command import ClickCommand
from results_utils import AddressBook
from snapshot import DeviceSnapshot
from task.app_task import AppTask
from adb_utils import launch_specified_application, get_most_recent_file, get_file_nums, download_android_file, logger
from consts import dir_path, dir_pref_path

class RecordUsecaseTask(AppTask):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.usecase_path = self.app_path.joinpath("usecase.jsonl")
        self.sugilite_script_path = self.app_path.joinpath("sugilite_script")

    async def execute(self):
        """
            The use case should be written in `usecase_path` where each line is the JSON representation of a
            `Command`. The initial state of the usecase should be stored in a `Snapshot` called "init"
        """
        # ---------- Setting up the initial snapshot ----------------
        init_snapshot = DeviceSnapshot(address_book=AddressBook(self.app_path.joinpath("init")),
                                       device=self.device)
        await init_snapshot.setup(first_setup=True)

        # ---------- Start recording ----------------
        # Launch Sugilite application based on the package name
        await launch_specified_application("edu.cmu.hcii.sugilite")
        prev_num_in_prefix = await get_file_nums(dir_pref_path)
        await get_most_recent_file(dir_pref_path, prev_num_in_prefix, 0.5)
        app_pkg_name=self.app_path.name
        # Start the recorded application based on the package name
        return_code=await launch_specified_application(app_pkg_name)

        # ----- Receive Sugilite's results
        prev_num = await get_file_nums(dir_path)
        # Wait to have the most recent file
        most_recent_name = await get_most_recent_file(dir_path, prev_num, 1)
        logger.debug('The most recent name is: ' + most_recent_name)
        dest_path = self.sugilite_script_path.resolve()
        if not dest_path.exists():
            os.makedirs(dest_path)
        return_code = await download_android_file(dir_path, most_recent_name, dest_path)
        await self.generate_usecase(most_recent_name)

    async def generate_usecase(self, most_recent_name):
        commands = []
        logger.debug("process the Sugilite script")
        for file in self.sugilite_script_path.resolve().iterdir():
            if file.name == most_recent_name:
                with open(file, 'r') as f:
                    for line in f:
                        message = json.loads(line)
                        # Converting to the ClickCommand
                        text = message['Text'] if 'Text' in message else ''
                        class_name = message['Class_Name'] if 'Class_Name' in message else ''
                        resource_id = message['Resource_ID'] if 'Resource_ID' in message else ''
                        content_desc = message['Content_Desc'] if 'Content_Desc' in message else ''
                        pkg_name = message['Package_Name'] if 'Package_Name' in message else ''
                        xpath = message['Xpath'] if 'Xpath' in message else ''

                        node_dict = {
                            'text': text,
                            'class_name': class_name,
                            'resource_id': resource_id,
                            'content_desc': content_desc,
                            'pkg_name': pkg_name,
                            'xpath': xpath
                        }

                        node = Node.createNodeFromDict(node_dict)
                        command = ClickCommand(node)
                        commands.append(command)

            # Once the commands is filled write it to usecase path
            with open(self.usecase_path, "w") as f:
                for command in commands:
                    f.write(f"{command.toJSONStr()}\n")
