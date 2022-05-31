#!/bin/bash
device_name=${1:-"emulator-5554"}
device_name_2=${2:-"emulator-5556"}
adb -s $device_name shell settings put secure enabled_accessibility_services dev.navids.latte/dev.navids.latte.app.MyLatteService
adb -s $device_name_2 shell settings put secure enabled_accessibility_services dev.navids.latte/dev.navids.latte.app.MyLatteService