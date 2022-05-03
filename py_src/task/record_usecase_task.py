import asyncio
import os
import re
from GUI_utils import Node
from command import ClickCommand
from results_utils import AddressBook
from snapshot import DeviceSnapshot
from task.app_task import AppTask
from adb_utils import *


class RecordUsecaseTask(AppTask):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.usecase_path = self.app_path.joinpath("usecase.jsonl")
        self.sugilite_script_path=self.app_path.joinpath("sugilite_script")

    async def execute(self):
        """
            The use case should be written in `usecase_path` where each line is the JSON representation of a
            `Command`. The initial state of the usecase should be stored in a `Snapshot` called "init"
        """
        # ---------- Setting up the initial snapshot ----------------
        init_snapshot = DeviceSnapshot(address_book=AddressBook(self.app_path.joinpath("init")),
                                       device=self.device)
        await init_snapshot.setup(first_setup=True)

        # ---------- Recording the usecase ----------------
        # TODO: Start Sugilite
        dir_path = "edu.cmu.hcii.sugilite/scripts"
        await start_android_application("edu.cmu.hcii.sugilite", "ui.main.SugiliteMainActivity")

        # ----- Wait for user to stops
        # TODO: Receive Sugilite's results
        prev_num = await get_file_nums(dir_path)
        # Wait to have the most recent file
        most_recent_name = await get_most_recent_file(dir_path, prev_num, 1)
        logger.debug('The most recent name is: '+most_recent_name)
        dest_path=self.sugilite_script_path.resolve()
        if not dest_path.exists():
            os.makedirs(dest_path)
        return_code = await download_recent_file(dir_path, most_recent_name,dest_path)

        # ------------ TODO: needs to be implemented ----------
        await self.generate_usecase(most_recent_name)

    async def generate_usecase(self,most_recent_name):
        commands = []
        logger.debug("process the Sugilite script")
        for file in self.sugilite_script_path.resolve().iterdir():
            if file.name==most_recent_name:
                with open(file, 'r') as f:
                    lines=f.readlines()
                    i=0
                    while i< len(lines):
                        text=re.sub(r"\"","",re.findall(r"\(hasText (.+?)\)",lines[i])[0]) if re.findall(r"\(hasText (.+?)\)",lines[i]) else ''
                        class_name=re.findall(r"\(HAS_CLASS_NAME (.+?)\)",lines[i])[0] if re.findall(r"\(HAS_CLASS_NAME (.+?)\)",lines[i]) else ''
                        resource_id=re.findall(r"\(HAS_VIEW_ID (.+?)\)",lines[i])[0] if re.findall(r"\(HAS_VIEW_ID (.+?)\)",lines[i]) else ''
                        content_desc=re.sub(r"\"","",re.findall(r"\(HAS_CONTENT_DESCRIPTION (.+?)\)",lines[i])[0]) if re.findall(r"\(HAS_CONTENT_DESCRIPTION (.+?)\)",lines[i]) else ''
                        xpath=re.findall(r"\(HAS_XPATH (.+?)\)",lines[i])[0] if re.findall(r"\(HAS_XPATH (.+?)\)",lines[i]) else ''
                        pkg_name=re.findall(r"\(HAS_PACKAGE_NAME (.+?)\)",lines[i])[0] if re.findall(r"\(HAS_PACKAGE_NAME (.+?)\)",lines[i]) else ''
                        if i>0:
                            prev_xpath=re.findall(r"\(HAS_XPATH (.+?)\)",lines[i-1])[0] if re.findall(r"\(HAS_XPATH (.+?)\)",lines[i-1]) else ''
                            if xpath==prev_xpath:
                                i+=1
                                continue
                        node_dict={
                            'text':text,
                            'class_name':class_name,
                            'resource_id':resource_id,
                            'content_desc':content_desc,
                            'pkg_name':pkg_name,
                            'xpath':xpath
                        }
                        node=Node.createNodeFromDict(node_dict)
                        command=ClickCommand(node)
                        commands.append(command)
                        i+=1

            # Once the commands is filled write it to usecase path
            with open(self.usecase_path, "w") as f:
                for command in commands:
                    f.write(f"{command.toJSONStr()}\n")


