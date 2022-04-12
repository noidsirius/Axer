import asyncio
import os
from results_utils import AddressBook
from snapshot import DeviceSnapshot
from task.app_task import AppTask
from adb_utils import *


class RecordUsecaseTask(AppTask):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.usecase_path = self.app_path.joinpath("usecase.jsonl")

    async def execute(self):
        """
            The use case should be written in `usecase_path` where each line is the JSON representation of a
            `Command`. The initial state of the usecase should be stored in a `Snapshot` called "init"
        """
        # ---------- Setting up the initial snapshot ----------------
        init_snapshot = DeviceSnapshot(address_book=AddressBook(self.app_path.joinpath("init")),
                                       device=self.device)
        # await init_snapshot.setup(first_setup=True)

        # ---------- Recording the usecase ----------------
        # TODO: Start Sugilite
        dir_path = "edu.cmu.hcii.sugilite/scripts"
        await start_android_application("edu.cmu.hcii.sugilite", "ui.main.SugiliteMainActivity")

        # ----- Wait for user to stops
        # TODO: Receive Sugilite's results
        prev_num = await get_file_nums(dir_path)
        # Wait to have the most recent file
        most_recent_name = await get_most_recent_file(dir_path, prev_num, 1)
        dest_dir = os.path.abspath(os.path.join(os.getcwd(), os.pardir)) + "\sugilite_script"
        return_code = await download_recent_file(dir_path, most_recent_name, dest_dir)

        # ------------ TODO: needs to be implemented ----------
        # sugilite_result_path = "..."
        commands = []
        # for each line in sugilite_result_path
            # create a command
                # A clickable command requires a Node
                # create a Node from dictionary
                # node_dict = {'class': '', 'text': ''}
                # node = Node.createNodeFromDict(node_dict)
                # command = ClickCommand(node)
                # commands.append(command)
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
