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
        dir="edu.cmu.hcii.sugilite/scripts"
        await start_android_application("edu.cmu.hcii.sugilite","ui.main.SugiliteMainActivity")

        # ----- Wait for user to stops
        # TODO: Receive Sugilite's results
        prev_num=await get_file_nums(dir)
        most_recent_name=await get_most_recent_file(dir,prev_num,1)
        dest_dir = os.path.abspath(os.path.join(os.getcwd(), os.pardir)) + "\sugilite_script"
        return_code=await download_recent_file(dir,most_recent_name,dest_dir)



async def start():
    content = RecordUsecaseTask(app_path="", device="")
    await content.execute()



if __name__=="__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(start())

