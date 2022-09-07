import asyncio
import json
import logging
from typing import List, Optional, Union

from adb_utils import install_application
from json_util import JSONSerializable
from shell_utils import run_bash

logger = logging.getLogger(__name__)

BASE_RECIPE_NAME = 'AP-Base-3'


async def send_gmsaas_command(command: str) -> Optional[dict]:
    ret_value, stdout, stderr = await run_bash(f"gmsaas --format json {command}")
    try:
        result = json.loads(stdout)
    except Exception as e:
        logger.error(f"The result was not JSON, RetValue: {ret_value}, STDOUT: '{stdout}', STDERR: '{stderr}', Exception: {e}")
        return None
    return result


class RecipeInfo(JSONSerializable):
    def __init__(self,
                 uuid: str,
                 name: str,
                 android_version: str = "0.0",
                 screen_width:int = 0,
                 screen_height: int = 0,
                 screen_density: int = 0,
                 screen: str = "UNKNOWN",
                 source: str = "UNKNOWN",
                 **kwargs):
        self.uuid = uuid
        self.name = name
        self.android_version = android_version
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.screen_density = screen_density
        self.screen = screen
        self.source = source


class GenymotionInstance(JSONSerializable):
    def __init__(self,
                 uuid: str,
                 name: str,
                 created_at: str,
                 state: str,
                 adbtunnel_state: str,
                 adb_serial: str,
                 adb_serial_port: int,
                 recipe: Union[dict,RecipeInfo],
                 **kwargs):
        if isinstance(recipe, dict):
            recipe = RecipeInfo(**recipe)
        self.uuid = uuid
        self.name = name
        self.created_at = created_at
        self.state = state
        self.adbtunnel_state = adbtunnel_state
        self.adb_serial = adb_serial
        self.adb_serial_port = adb_serial_port
        self.recipe = recipe

    def _update_state(self, **instance_info) -> bool:
        updated_instance_info = GenymotionInstance(**instance_info)
        if updated_instance_info.uuid == self.uuid and updated_instance_info.name == self.name:
            self.state = updated_instance_info.state
            self.adbtunnel_state = updated_instance_info.adbtunnel_state
            self.adb_serial_port = updated_instance_info.adb_serial_port
            return True
        logger.error(f"The updated instance is not the same, Received Instance: {updated_instance_info}, This Instance: {self}")
        return False

    async def update_state(self) -> bool:
        result = await send_gmsaas_command(f"instances get {self.uuid}")
        if result is None or 'instance' not in result:
            return False
        instance_info = result['instance']
        return self._update_state(**instance_info)

    async def connect_adb(self) -> bool:
        result = await send_gmsaas_command(f"instances adbconnect {self.uuid}")
        if result is None or 'instance' not in result:
            return False
        instance_info = result['instance']
        return self._update_state(**instance_info)

    def is_online(self):
        return self.state == 'ONLINE'

    def get_adb_device_name(self) -> Optional[str]:
        if self.adbtunnel_state == 'CONNECTED':
            if self.adb_serial == '0.0.0.0':
                return f"localhost:{self.adb_serial_port}"   # TODO: Not sure why it happens
            return self.adb_serial
        return None

    async def stop(self) -> bool:
        result = await send_gmsaas_command(f'instances stop {self.uuid}')
        if result is None or 'instance' not in result:
            return False
        return self._update_state(**result['instance'])


async def list_recipes() -> List[RecipeInfo]:
    result = await send_gmsaas_command("recipes list")
    if result is None or 'recipes' not in result:
        return []
    recipes = []
    for info in result['recipes']:
        recipes.append(RecipeInfo(**info))
    return recipes


async def get_recipe(name: str) -> Optional[RecipeInfo]:
    for recipe in await list_recipes():
        if recipe.name == name:
            return recipe
    return None


async def list_instances() -> List[GenymotionInstance]:
    result = await send_gmsaas_command("instances list")
    if result is None or 'instances' not in result:
        return []
    instances = []
    for info in result['instances']:
        instances.append(GenymotionInstance(**info))
    return instances


async def create_instance(instance_name: str, recipe: RecipeInfo = None) -> Optional[GenymotionInstance]:
    if recipe is None:
        recipe = await get_recipe(BASE_RECIPE_NAME)
    logger.debug(f"Creating instance {instance_name} from Recipe: {recipe.name}")
    result = await send_gmsaas_command(f"instances start {recipe.uuid} {instance_name}")
    if result is None or 'instance' not in result:
        return None
    instance_info = result['instance']
    instance = GenymotionInstance(**instance_info)
    logger.debug(f"Instance {instance.name} is created!")
    return instance


async def stop_instances():
    logger.debug("Stopping genymotion instances")
    stop_tasks = []
    for instance in await list_instances():
        stop_tasks.append(asyncio.create_task(instance.stop()))
    await asyncio.wait(stop_tasks)
    logger.debug("All genymotion instances are stopped!")


async def setup_ap_instance(instance_name: str, app_paths : List[str] = None) -> bool:
    if app_paths is None:
        app_paths = []
    instance = await create_instance(instance_name=instance_name)
    if instance is None or not instance.is_online():
        logger.error(f"Instance {instance_name} could not be created")
        return False
    if not await instance.connect_adb():
        logger.error(f"ADB could not be connected for {instance_name}")
        await instance.stop()
        return False
    logger.info(f"Instance {instance.name} is created, ADB: {instance.get_adb_device_name()}")
    for app_path in app_paths:
        logger.debug(f"Installing {app_path} on {instance.name}")
        if not await install_application(apk_path=app_path, device_name=instance.get_adb_device_name()):
            logger.error(f"App {app_path} could not be installed on {instance.name}")
            await instance.stop()
            return False

    return True




