from typing import Any
import asyncio
import aiofiles
from consts import BLIND_MONKEY_TAG


async def save_screenshot(device, file_name) -> None:
    result = await device.screencap()
    await asyncio.sleep(2) # TODO: Configurable
    async with aiofiles.open(file_name, mode='wb') as f:
        await asyncio.sleep(2)
        await f.write(result)
    await asyncio.sleep(2)
    return file_name


class ParallelADBLogger:
    def __init__(self, device):
        self.device = device
        self.lock = None
        self.log_message = ""

    async def _logcat(self):
        async def logcat_handler(connection):
            global log_list
            while True:
                data = await connection.read(1024)
                if not data:
                    break
                self.log_message += data.decode('utf-8')
            await connection.close()
        conn = await self.device.create_connection(timeout=None)
        cmd = "shell:{}".format("logcat -c; logcat")
        await conn.send(cmd)
        await logcat_handler(conn)

    async def execute_async_with_log(self, coroutine_obj: asyncio.coroutine) -> (str, Any):
        if self.lock is not None:
            raise Exception("Cannot execute more than one coroutine while logging!")
        self.lock = coroutine_obj
        self.log_message = ""
        ll_task = asyncio.create_task(self._logcat())
        coroutine_result = await coroutine_obj
        await asyncio.sleep(0.5)
        ll_task.cancel()
        self.lock = None
        self.log_message = "\n".join(line for line in self.log_message.split("\n") if BLIND_MONKEY_TAG in line)
        return self.log_message, coroutine_result
