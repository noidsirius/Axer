LAYOUT=$(adb exec-out uiautomator dump /dev/tty)
FOO="UI hierchary dumped to: /dev/tty"
LAYOUT=${LAYOUT//"$FOO"/""}
echo "$LAYOUT"
