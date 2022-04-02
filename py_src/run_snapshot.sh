#!/bin/bash
SNAPSHOT_TIMEOUT=240
SNAPSHOT=$1
RESULT_PATH=${2:-$(realpath ../dev_results)}
RESULT_PATH=$(realpath "$RESULT_PATH")
DIRECTIONAL_ACTION_LIMIT="--dir-action-limit 5"
POINT_ACTION_LIMIT="--point-action-limit 2"
#OVERSIGHT="--oversight"
OVERSIGHT=""
MODE=${3:-""}
APP_NAME=${SNAPSHOT%%.S_*}
echo "Snapshot $SNAPSHOT in App $APP_NAME"
 gtimeout $SNAPSHOT_TIMEOUT python main.py --app-name "$APP_NAME" --output-path "$RESULT_PATH" --snapshot "$SNAPSHOT" --debug $DIRECTIONAL_ACTION_LIMIT $POINT_ACTION_LIMIT $OVERSIGHT $MODE
TMP_SNAPSHOT=$SNAPSHOT"_TMP"
adb emu avd snapshot delete "$TMP_SNAPSHOT"
rm -rf ~/.android/avd/Pixel_Stoat.avd/snapshots/"$TMP_SNAPSHOT"
echo "REMOVE $TMP_SNAPSHOT"
