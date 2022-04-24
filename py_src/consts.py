import os

# Timeout Time
LAYOUT_TIMEOUT_TIME = 3
TB_NAVIGATE_TIMEOUT = 4
TB_SELECT_TIMEOUT = 4
REGULAR_EXECUTE_TIMEOUT_TIME = 6
IS_LIVE_TIMEOUT_TIME = 1
# Delays
CAPTURE_SCREENSHOT_DELAY = 5
CAPTURE_STATE_DELAY = 3
REGULAR_EXECUTOR_INTERVAL = 1000
TB_EXECUTOR_INTERVAL = 1000
# Retry
TB_NAVIGATE_RETRY_COUNT = 3
ACTION_EXECUTION_RETRY_COUNT = 2
# Tags
BLIND_MONKEY_TAG = "LATTE_SERVICE"
BLIND_MONKEY_EVENTS_TAG = "LATTE_A11Y_EVENT_TAG"
BLIND_MONKEY_INSTRUMENTED_TAG = "BM_INSTRUMENTED"
TB_TREELIST_TAG = "talkback: TreeDebug:"
# Other Limits
EXPLORE_VISIT_LIMIT = 3
# Others
DEVICE_NAME = "emulator-5554"
# DEVICE_NAME = "192.168.1.46:39415"
ADB_HOST = "127.0.0.1"
ADB_PORT = 5037
UIED_PATH = os.getenv('UIED_PATH', None)
