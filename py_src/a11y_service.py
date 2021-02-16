import asyncio
from typing import List
from adb_utils import run_bash


class A11yServiceManager:
    services = {"tb": "com.google.android.marvin.talkback/com.google.android.marvin.talkback.TalkBackService",
                         "latte": "dev.navids.latte/dev.navids.latte.app.MyLatteService"}

    @staticmethod
    async def get_enabled_services() -> List[str]:
        _, enabled_services, _ = await run_bash("adb shell settings get secure enabled_accessibility_services")
        if 'null' in enabled_services:
            return []
        return enabled_services.strip().split(':')

    @staticmethod
    async def is_enabled(service_name: str) -> bool:
        if service_name not in A11yServiceManager.services:
            return False
        enabled_services = await A11yServiceManager.get_enabled_services()
        return A11yServiceManager.services[service_name] in enabled_services

    @staticmethod
    async def enable(service_name: str) -> bool:
        if service_name not in A11yServiceManager.services:
            return False
        enabled_services = await A11yServiceManager.get_enabled_services()
        if A11yServiceManager.services[service_name] in enabled_services:
            return True
        enabled_services_str = ":".join(enabled_services + [A11yServiceManager.services[service_name]])
        r_code, *_ = await run_bash(
            f"adb shell settings put secure enabled_accessibility_services {enabled_services_str}")
        return r_code == 0

    @staticmethod
    async def disable(service_name: str) -> bool:
        if service_name not in A11yServiceManager.services:
            return False
        enabled_services = await A11yServiceManager.get_enabled_services()
        if A11yServiceManager.services[service_name] not in enabled_services:
            return True
        enabled_services.remove(A11yServiceManager.services[service_name])
        enabled_services_str = ":".join(enabled_services)
        if len(enabled_services_str) == 0:
            r_code, *_ = await run_bash(
                f"adb shell settings delete secure enabled_accessibility_services")
        else:
            r_code, *_ = await run_bash(
                f"adb shell settings put secure enabled_accessibility_services {enabled_services_str}")
        return r_code == 0

    @staticmethod
    async def setup_latte_a11y_services(tb=False) -> None:
        if tb:
            await A11yServiceManager.enable("tb")
        else:
            await A11yServiceManager.disable("tb")
        if not await A11yServiceManager.is_enabled("latte"):
            await A11yServiceManager.enable("latte")
            await asyncio.sleep(1)
