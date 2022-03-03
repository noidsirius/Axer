#!/bin/bash
FLAG=0
RESULT_PATH=$(realpath ../selected3_results)
LAST_APK_FILE="checkout"
for APK_FILE in ../BM_APKs/selected_apks/*.apk; do
	if [ "$(basename "$APK_FILE")" = "$LAST_APK_FILE.apk" ]; then
		FLAG=1
	fi
	if [ $FLAG -eq 0 ]; then
		continue
	fi
	adb kill-server
	adb start-server
	../scripts/remove_snapshots.sh YES
	./run_single.sh "$APK_FILE" "$RESULT_PATH"
done

