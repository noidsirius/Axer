#!/bin/bash
FLAG=1
RESULT_PATH=`realpath ../new_format_result`
LAST_APK_FILE="me.lyft.android"
for APK_FILE in `ls ../BM_APKs/small_apks/*.apk`; do
	if [ `basename $APK_FILE` = "$LAST_APK_FILE.apk" ]; then
		FLAG=1
	fi
	if [ $FLAG -eq 0 ]; then
		continue
	fi
	deactivate
	APK_PATH=`realpath $APK_FILE`
	echo "Running APK $APK_FILE"
  ../scripts/load_snapshot.sh BASE
	../scripts/remove_snapshots.sh YES
	echo "Sleep 5 seconds"
	sleep 5
	~/Workspaces/python/Stoat/explore.sh $APK_PATH # TODO: Make the path variable
	source ../.env/bin/activate
	for SNAPSHOT in `../scripts/list_snapshots.sh`; do
	  APP_NAME=${SNAPSHOT%%_*}
		echo "Snapshot $SNAPSHOT in App $APP_NAME"
		python main.py --app-name $APP_NAME --output-path $RESULT_PATH --snapshot $SNAPSHOT --debug
		python post_analysis.py --snapshot-path $RESULT_PATH/$APP_NAME/$SNAPSHOT --name INITIAL
		TMP_SNAPSHOT=$SNAPSHOT"_TMP"
		adb emu avd snapshot delete $TMP_SNAPSHOT
		rm -rf ~/.android/avd/Pixel_Stoat.avd/snapshots/$TMP_SNAPSHOT
		echo "REMOVE $TMP_SNAPSHOT"
	done
done

