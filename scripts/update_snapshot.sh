#!/bin/bash
SNAPSHOT_NAME=$1
$LATTE_PATH/scripts/load_snapshot.sh $SNAPSHOT_NAME
sleep 2
adb install -r -g $LATTE_PATH/Setup/Latte.apk
$LATTE_PATH/scripts/save_snapshot.sh $SNAPSHOT_NAME

