#!/bin/bash
FLAG=1
RESULT_PATH=$(realpath ../az_results)
LAST_APK_FILE="at.jclehner.rxdroid"
for APK_FILE in ../BM_APKs/androzoo_apks/*.apk; do
	if [ "$(basename "$APK_FILE")" = "$LAST_APK_FILE.apk" ]; then
		FLAG=1
	fi
	if [ $FLAG -eq 0 ]; then
		continue
	fi
	../scripts/remove_snapshots.sh YES
	./run_single.sh "$APK_FILE" "$RESULT_PATH"
done

