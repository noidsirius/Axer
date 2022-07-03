#!/bin/bash
INTENT=dev.navids.latte.COMMAND
CMD=$1
EXTRA=${2:-NONE}
device_name=${3:-"emulator-5554"}
device_name2=${4:-"emulator-5558"}
EXTRA=${EXTRA//\"/\_\_\^\_\_}
EXTRA=${EXTRA//[[:space:]]/\_\_\^\^\_\_}
EXTRA=${EXTRA//\,/\_\_\^\^\^\_\_}
EXTRA=${EXTRA//\'/\_\_\^\_\^\_\_}
EXTRA=${EXTRA//\+/\_\_\^\-\^\_\_}
EXTRA=${EXTRA//\|/\_\_\^\^\^\^\_\_}
EXTRA=${EXTRA//\$/\_\_\^\_\^\^\_\_}
EXTRA=${EXTRA//\*/\_\_\^\-\^\^\_\_}
EXTRA=${EXTRA//\&/\_\_\^\^\_\^\_\_}
echo $EXTRA
echo "Send command '$CMD' to LatteService in device $device_name2"
adb -s $device_name2 shell am broadcast -a dev.navids.latte.COMMAND --es command "$CMD" --es extra "$EXTRA"
