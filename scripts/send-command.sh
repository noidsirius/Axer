#!/bin/bash
INTENT=dev.navids.latte.COMMAND
CMD=$1
EXTRA=${2:-NONE}
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
echo "Send command '$CMD' to LatteService"
adb shell am broadcast -a dev.navids.latte.COMMAND --es command "$CMD" --es extra "$EXTRA"
