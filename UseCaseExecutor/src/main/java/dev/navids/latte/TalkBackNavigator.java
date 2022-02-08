package dev.navids.latte;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.os.Handler;
import android.util.Log;
import android.view.accessibility.AccessibilityNodeInfo;

import org.json.JSONObject;

import java.io.File;
import java.util.HashMap;
import java.util.Map;

// TODO: Why it doesn't use Navigator interface?
public class TalkBackNavigator {
    private static TalkBackNavigator instance;
    private TalkBackNavigator(){}
    public static TalkBackNavigator v(){
        if(instance == null)
            instance = new TalkBackNavigator();
        return instance;
    }
    // TODO: Needs to be removed
    private Map<Integer, String> pendingActions = new HashMap<>();
    private int pendingActionId = 0;

    public boolean isPending(){
        return pendingActions.size() > 0 || ActionUtils.isActionPending();
    }

    public void interrupt(){
        pendingActions.clear(); // TODO: Do we need to cancel the pending actions somehow?
        ActionUtils.interrupt();
        Utils.createFile(Config.v().FINISH_ACTION_FILE_PATH, "INTERRUPT"); // TODO: make consistent with custom step
    }

    public boolean performNext(Navigator.DoneCallback doneCallback){
        Log.i(LatteService.TAG, "performNext");
        if (!ActionUtils.swipeRight(doneCallback))
        {
            Log.i(LatteService.TAG, "There is a problem with swiping right");
            return false;
        }
        return true;
    }

    public boolean logTalkBackTreeNodeList(Navigator.DoneCallback doneCallback){
        Log.i(LatteService.TAG, "perform Up then Left");
        if (!ActionUtils.swipeUpThenLeft(doneCallback))
        {
            Log.i(LatteService.TAG, "There is a problem with swiping Up then Left");
            return false;
        }
        return true;
    }

    public boolean performSelect(Navigator.DoneCallback doneCallback){
        Log.i(LatteService.TAG, "performSelect");
        if(isPending()){
            Log.i(LatteService.TAG, String.format("Do nothing since another action is pending! (Size:%d)", pendingActions.size()));
            return false;
        }
        final int thisActionId = pendingActionId;
        pendingActionId++;
        pendingActions.put(thisActionId, "Pending: I'm going to perform Select");
        AccessibilityService.GestureResultCallback callback = new AccessibilityService.GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription gestureDescription) {
                new Handler().postDelayed(() -> {
                    pendingActions.remove(thisActionId);
                    if(doneCallback != null)
                        doneCallback.onCompleted(LatteService.getInstance().getFocusedNode());
                }, Config.v().FOCUS_CHANGE_TIME);
            }

            @Override
            public void onCancelled(GestureDescription gestureDescription) {
                Log.i(LatteService.TAG, "Performing Select is cancelled!");
                pendingActions.remove(thisActionId);
                if(doneCallback != null)
                    doneCallback.onError("Performing Select is cancelled!");
            }
        };
        ActionUtils.performDoubleTap(callback);
        return true;
    }


    public boolean selectFocus(Navigator.DoneCallback doneCallback) {
        Utils.deleteFile(Config.v().FINISH_ACTION_FILE_PATH);
        AccessibilityNodeInfo focusedNode = LatteService.getInstance().getFocusedNode();
        boolean result = performSelect(new Navigator.DoneCallback() {
            @Override
            public void onCompleted(AccessibilityNodeInfo nodeInfo) {
                WidgetInfo newWidgetNodeInfo = ActualWidgetInfo.createFromA11yNode(focusedNode);
                Log.i(LatteService.TAG, "The focused node is tapped: " + focusedNode);
                // TODO: Change the formatting to use JSON
                Utils.createFile(Config.v().FINISH_ACTION_FILE_PATH,
                        String.format("Custom Step $ State: COMPLETED $ #Events: 1 $ Time: - $ ActingWidget: %s",newWidgetNodeInfo.completeToString(true)));
                if(doneCallback != null)
                    doneCallback.onCompleted(nodeInfo);
            }

            @Override
            public void onError(String message) {
                Log.i(LatteService.TAG, "Cancel in double tapping!");
                if(doneCallback != null)
                    doneCallback.onError(message);
            }
        });
        return result;
    }

    public void clearHistory(){
        String dir = LatteService.getInstance().getBaseContext().getFilesDir().getPath();
        new File(dir, Config.v().FINISH_ACTION_FILE_PATH).delete();
    }

    public boolean nextFocus(Navigator.DoneCallback callback) {
        Utils.deleteFile(Config.v().FINISH_ACTION_FILE_PATH);
        WidgetInfo widgetInfo = ActualWidgetInfo.createFromA11yNode(LatteService.getInstance().getFocusedNode());
        Log.i(LatteService.TAG, String.format("Widget %s is visited XPATH: %s.", widgetInfo, widgetInfo != null ? widgetInfo.getAttr("xpath") : "NONE"));
        boolean result = performNext(new Navigator.DoneCallback() {
            @Override
            public void onCompleted(AccessibilityNodeInfo nodeInfo) {
                WidgetInfo newWidgetNodeInfo = ActualWidgetInfo.createFromA11yNode(nodeInfo, true);
                Log.i(LatteService.TAG, "The next focused node is: " + newWidgetNodeInfo + " Xpath: " + newWidgetNodeInfo.getXpath());
                JSONObject jsonCommand = newWidgetNodeInfo.getJSONCommand("xpath", false, "click");
                String jsonCommandStr = jsonCommand != null ? jsonCommand.toString() : "Error";
                Utils.createFile(Config.v().FINISH_ACTION_FILE_PATH, jsonCommandStr);
                if(callback != null)
                    callback.onCompleted(nodeInfo);
            }

            @Override
            public void onError(String message) {
                Log.i(LatteService.TAG, "Error in next: " + message);
                if(callback != null)
                    callback.onError(message);
            }
        });
        return result;
    }

    public void currentFocus() {
        Utils.deleteFile(Config.v().FINISH_ACTION_FILE_PATH);
        WidgetInfo widgetInfo = ActualWidgetInfo.createFromA11yNode(LatteService.getInstance().getFocusedNode());
        Log.i(LatteService.TAG, "The focused node is: " + widgetInfo + " Xpath: " + widgetInfo.getXpath());
        JSONObject jsonCommand = widgetInfo.getJSONCommand("xpath", false, "click");
        String jsonCommandStr = jsonCommand != null ? jsonCommand.toString() : "Error";
        Utils.createFile(Config.v().FINISH_ACTION_FILE_PATH, jsonCommandStr);
    }
}
