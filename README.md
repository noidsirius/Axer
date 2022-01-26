# BlindMonkey
## Setup
-  Install python packages `pip install -r requirements.txt`
- Initialize an Android Virtual Device (AVD) with SDK +28 and name it `testAVD_1`
-	Disable soft main keys and virtual keyboard by adding `hw.mainKeys=yes` and `hw.kayboard=yes`  to `~/.android/avd/testAVD_1.avd/config.ini`
	- If virtual device is not disabled, please follow this [link](https://support.honeywellaidc.com/s/article/CN51-Android-How-to-prevent-virtual-keyboard-from-popping-up)
- Enable "Do not disturb" in the emulator to avoid notifications during testing (it can be found at the top menu)
- Install TalkBack, the latest version (9.1) can be found in `Setup/talkback.apk` (`adb install Setup/talkback.apk`)
- Build Latte Service APK by running `./build_latte_lib`, then install it (`adb install -r -g Setup/latte.apk`) or install from Android Studio
	- To check if the installation is correct, first run the emulator and then execute `./scripts/enable-talkback.sh` (by clicking on a GUI element it should be highlighted). 
	- Also, execute `./scripts/send-command.sh log` and check Android logs to see if Latte prints the AccessibilityNodeInfos of GUI element on the screen (`adb logcat | grep "LATTE_SERVICE"`)
-  Save the base snapshot by `./scripts/save_snapshot.sh BASE`

## Latte CLI
You can interact with Latte by sending commands to its Broadcast Receiver or receive generated information from Latte by reading files from the local storage. First, you need to enable Latte by running `./scritps/enable-service.sh`, then you can send command by running `./scripts/send-command.sh <COMMAND> <EXTRA>`. If you want to work with TalkBack, first you need to enable it by running `./scritps/enable-talkback.sh`. If any command has an output written in a file, you can use `./scripts/wait_for_file.sh <FILE_NAME>` which prints the content of the file and removes it. It's encouraged to watch the logs in a separate terminal `adb logcat | grep "LATTE_SERVICE"`. Here is the list of all commands:
- **General**
	- `log`: Prints the current layout's xpaths in Android logs.
	- `capture_layout`: Dumps the XML file of the current layout. Output's file name: `a11y_layout.xml`
	- `report_a11y_issues`: Prints the accessibility issues (reported by Accessibility Testing Framework) in Android logs.

- **TalkBack Navigation**
	- `nav_next`: Navigates the focused element to the next element. Output's file name: `finish_nav_action.txt`
	- `nav_select`: Selects the focused element (equivalent to Tap). Output's file name: `finish_nav_action.txt`
	- `nav_interrupt`: Interrupt the current navigation action
	- `nav_clear_history`: In case the last navigation result is not removed.
- **UseCase Executor**
	- `enable`/`disable`: Enable/Disable the use-case executor component
	- `set_delay`: Sets the time for each interval (cycle).
	- `set_step_executor`: Sets the driver (step_executor). The extra can be `talkback`, `regular` (touch based), `sighted_tb` (touch based TalkBack).
	- `set_physical_touch`: If the extra is 'true', the regular executor emulates *touch*, otherwise it uses A11yNodeInfo events to perform actions.
	- `do_step`: Performs a single step where the step is provided in extra.
	- `interrupt`: Interrupts the current step execution
	- `init`: Initializes a use case, the use case speicfication is provided in extra.
	- `start`: Starts the use case (`init` must be called beforehand)
	- `stop`: Stops the current use case execution

## BlindMonkey
To analyze a snapshot, first load the BASE snapshot `./scripts/load_snapshot.sh BASE`, then install the app under test, and go to the screen that you want to analyze. Next, creates a new snapshot by `./scripts/save_snapshot.sh <SNAPSHOT>`. Now you can run the BlindMonkey on this snapshot by running
```
python pt_src/main.py --app-name <APP_NAME> --output-path <RESLUT_PATH> --snapshot <SNAPSHOT> --debug
```



## OLD ---- Run SnapA11yIssueDetector
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

## OLD ------ Use Library
- Create an app
- Add dependency (AAR)
- Add accessibility_service_config
    - Add string in xml
- Create a service and inherits from LatteService
- if no activity, change the default launch option to nothing
- TODO: Change enable-service and disable-service

##  OLD ------- Communication Service
- Http android:usesCleartextTraffic="true"
-