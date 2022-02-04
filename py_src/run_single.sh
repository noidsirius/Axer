#!/bin/bash
RESULT_PATH=$(realpath ../dev_results)
APK_PATH=$1
APK_PATH=$(realpath "$APK_PATH")
RESULT_PATH=${2:-$(realpath ../dev_results)}
RESULT_PATH=$(realpath "$RESULT_PATH")
APK_NAME=$(basename "$APK_PATH")
APK_NAME="${APK_NAME%.*}"
deactivate
echo "Running APK $APK_NAME, the result will be written in $RESULT_PATH"
../scripts/load_snapshot.sh BASE
echo "Sleep 5 seconds"
sleep 5
~/Workspaces/python/Stoat/explore.sh "$APK_PATH" # TODO: Make the path variable
source ../.env/bin/activate
for SNAPSHOT in $(../scripts/list_snapshots.sh); do
  APP_NAME=${SNAPSHOT%%_*}
  if [[ "$APP_NAME" != *"$APK_NAME"* ]]; then
    continue
  fi
  echo "Snapshot $SNAPSHOT in App $APP_NAME"
    python main.py --app-name "$APP_NAME" --output-path "$RESULT_PATH" --snapshot "$SNAPSHOT" --debug
  #		python post_analysis.py --snapshot-path $RESULT_PATH/$APP_NAME/$SNAPSHOT --name V1
    TMP_SNAPSHOT=$SNAPSHOT"_TMP"
    adb emu avd snapshot delete "$TMP_SNAPSHOT"
    rm -rf ~/.android/avd/Pixel_Stoat.avd/snapshots/"$TMP_SNAPSHOT"
    echo "REMOVE $TMP_SNAPSHOT"
done

