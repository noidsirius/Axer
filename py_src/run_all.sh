#!/bin/bash
FLAG=0
LAST_APK_FILE="me.lyft.android"
for APK_FILE in `ls ../BM_APKs/large_apks/*.apk`; do
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
	~/Workspaces/python/Stoat/explore.sh $APK_PATH
	source ../.env/bin/activate
	for x in `../scripts/list_snapshots.sh`; do
		echo "Snapshot: $x"
		python main.py $x
		A=$x"_TMP"
		adb emu avd snapshot delete $A
		rm -rf ~/.android/avd/Pixel_Stoat.avd/snapshots/$A
		echo "REMOVE $A"
	done
done
