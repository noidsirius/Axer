# BlindMonkey
## Setup
- Initialize an Android Virtual Device (AVD) with SDK +28 and name it `testAVD_1`
-	Disable soft main keys and virtual keyboard by adding `hw.mainKeys=yes` and `hw.kayboard=yes`  to `~/.android/avd/testAVD_1.avd/config.ini`
	- If virtual device is not disabled, please follow this [link](https://support.honeywellaidc.com/s/article/CN51-Android-How-to-prevent-virtual-keyboard-from-popping-up)
- Enable "Do not disturb" in the emulator to avoid notifications during testing (it can be found at the top menu)
- Install TalkBack, the latest version (9.1) can be found in `Setup/talkback.apk` (`adb install Setup/talkback.apk`)
- Install Latte service, either install the apk (`adb install Setup/latte.apk`) or install from Android Studio
	- To check if the installation is correct, first run the emulator and then execute `./scripts/enable-talkback.sh` (by clicking on a GUI element it should be highlighted). 
	- Also, execute `./scripts/send-command.sh log` and check Android logs to see if Latte prints the AccessibilityNodeInfos of GUI element on the screen (`adb logcat | grep "LATTE_SERVICE"`)
-  Save the base snapshot by `./scripts/save_snapshot.sh BASE`
-  Install python packages `pip install -r requirements.txt`

## Run SnapA11yIssueDetector
- Load the base snapshot by `./scripts/load_snapshot.sh BASE`
- Install the app you want to test, for example: `adb install -r -g Setup/yelp.apk`
- Run the app and go to a state you want to test, then take a snapshot, for example: `adb shell monkey -p com.yelp.android 1` and `./scripts/save_snapshot.sh Yelp_0`
- Run SnapA11yIssueDetector by executing `cd py_src && python main.py Yelp_0`
- Once the script is done, you can analyze the result using following python script:

```
from snapshot import Snapshot
snapshot = Snapshot("Yelp_0")
different_behaviors, directional_unreachable, unlocatable, different_behaviors_directional_unreachable = snapshot.report_issues()
```

## Use Library
- Create an app
- Add dependency (AAR)
- Add accessibility_service_config
    - Add string in xml
- Create a service and inherits from LatteService
- if no activity, change the default launch option to nothing
- TODO: Change enable-service and disable-service

## Communication Service
- Http android:usesCleartextTraffic="true"
-
