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
        self.sugilite_results_dir = self.app_path.joinpath("sugilite_script")

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
        self.sugilite_results_dir.mkdir(exist_ok=True)
        return_code = await download_recent_file(dir_path, most_recent_name, self.sugilite_results_dir.resolve())
        logger.info(f"Sugilite files are downloaded!")

        # ------------ TODO: needs to be implemented ----------
        await self.generate_usecase()

    async def generate_usecase(self):
        sugilite_result_path = "sugilite_script"
        commands = []
        for file_path in self.sugilite_results_dir.iterdir():
            with open(file_path, 'r') as f:
                for line in f:
                    text=re.findall(r"\(hasText \"(.+?)\"\)",line)[0] if re.findall(r"\(hasText \"(.+?)\"\)",line) else ''
                    class_name=re.findall(r"\(HAS_CLASS_NAME (.+?)\)",line)[0] if re.findall(r"\(HAS_CLASS_NAME (.+?)\)",line) else ''
                    resource_id=re.findall(r"\(HAS_VIEW_ID (.+?)\)",line)[0] if re.findall(r"\(HAS_VIEW_ID (.+?)\)",line) else ''
                    content_desc=re.sub(r"\"","",re.findall(r"\(HAS_CONTENT_DESCRIPTION (.+?)\)",line)[0]) if re.findall(r"\(HAS_CONTENT_DESCRIPTION (.+?)\)",line) else ''
                    xpath=re.findall(r"\(HAS_XPATH (.+?)\)",line)[0] if re.findall(r"\(HAS_XPATH (.+?)\)",line) else ''
                    pkg_name=re.findall(r"\(HAS_PACKAGE_NAME (.+?)\)",line)[0] if re.findall(r"\(HAS_PACKAGE_NAME (.+?)\)",line) else ''
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
                    logger.info(f"Command {command} is received from Sugilite!")
                    commands.append(command)
            # os.remove(os.path.join(sugilite_result_path, file_path))

            # Once the commands is filled write it to usecase path
            with open(self.usecase_path, "w") as f:
                for command in commands:
                    f.write(f"{command.toJSONStr()}\n")




async def start():
    content = RecordUsecaseTask(app_path="", device="")
    await content.execute()


if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(start())
