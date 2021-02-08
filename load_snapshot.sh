echo "Load snapshot: $1"
adb emu avd snapshot load $1 | grep "OK" && exit 0 || echo "Error!" && exit 1
