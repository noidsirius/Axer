package dev.navids.latte;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.os.Handler;
import android.util.Log;
import android.view.accessibility.AccessibilityNodeInfo;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;

public class TalkBackNavigator {
    private static TalkBackNavigator instance;
    private TalkBackNavigator(){}
    public static TalkBackNavigator v(){
        if(instance == null)
            instance = new TalkBackNavigator();
        return instance;
    }
    private Map<Integer, String> pendingActions = new HashMap<>();
    private int pendingActionId = 0;

    public boolean isPending(){
        return pendingActions.size() > 0;
    }

    public void interrupt(){
        pendingActions.clear(); // TODO: Do we need to cancel the pending actions somehow?
        Utils.createFile(Config.v().FINISH_ACTION_FILE_PATH, "INTERRUPT"); // TODO: make consistent with custom step
    }

    public boolean performNext(Navigator.DoneCallback doneCallback){
        Log.i(LatteService.TAG, "performNext");
        if(isPending()){
            Log.i(LatteService.TAG, String.format("Do nothing since another action is pending! (Size:%d)", pendingActions.size()));
            return false;
        }
        final int thisActionId = pendingActionId;
        pendingActionId++;
        pendingActions.put(thisActionId, "Pending: I'm going to do NEXT");
        AccessibilityService.GestureResultCallback callback = new AccessibilityService.GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription gestureDescription) {
                new Handler().postDelayed(() -> {
                    pendingActions.remove(thisActionId);
                    if(doneCallback != null)
                        doneCallback.onCompleted(LatteService.getInstance().getFocusedNode());
                }, Config.v().GESTURE_FINISH_WAIT_TIME);

            }

            @Override
            public void onCancelled(GestureDescription gestureDescription) {
                Log.i(LatteService.TAG, "Gesture is cancelled!");
                pendingActions.remove(thisActionId);
                if(doneCallback != null)
                    doneCallback.onError("Gesture is cancelled!");
            }
        };

        new Handler().postDelayed(() -> {
            GestureDescription.Builder gestureBuilder = new GestureDescription.Builder();
            Path swipePath = new Path();
            Random random = new Random();
            int BASE = 5;
            int dx1 = random.nextInt(2 * BASE) - BASE;
            int dx2 = random.nextInt(2 * BASE) - BASE;
            int dy1 = random.nextInt(2 * BASE) - BASE;
            int dy2 = random.nextInt(2 * BASE) - BASE;
            int x1 = 50 + dx1;
            int x2 = 500 + dx2;
            int y1 = 500 + dy1;
            int y2 = 600 + dy2;
            swipePath.moveTo(x1, y1);
            swipePath.lineTo(x2, y2);
            gestureBuilder.addStroke(new GestureDescription.StrokeDescription(swipePath, 0, Config.v().GESTURE_DURATION));
            GestureDescription gestureDescription = gestureBuilder.build();
            Log.i(LatteService.TAG, "Execute Gesture " + gestureDescription.toString());
            LatteService.getInstance().dispatchGesture(gestureDescription, callback, null);
        }, 10);
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
}
