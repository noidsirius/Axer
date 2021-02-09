package dev.navids.latte;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.os.Handler;
import android.service.controls.templates.ControlTemplate;
import android.util.Log;
import android.view.accessibility.AccessibilityNodeInfo;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;

public class TalkBackNavigator {
    private Map<Integer, String> pendingActions = new HashMap<>();
    private int pendingActionId = 0;
    private final long GESTURE_DURATION = 400; // TODO: Configuratble
    private final long WAIT_DURATION_TO_GET_RESULT = 400; // TODO: Configuratble
    private Set<WidgetInfo> visitedWidgets = new HashSet<>();
    private List<WidgetInfo> orderedVisitiedWidgets = new ArrayList<>();
    private String FINISH_NAVIGATION_FILE_PATH = "finish_nav_result.txt";
    private String FINISH_ACTION_FILE_PATH = "finish_nav_action.txt";

    // TODO: Do we need callback?
    private boolean performNext(Navigator.DoneCallback doneCallback){
        Log.i(LatteService.TAG, "performNext");
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
                }, WAIT_DURATION_TO_GET_RESULT);

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
            gestureBuilder.addStroke(new GestureDescription.StrokeDescription(swipePath, 0, GESTURE_DURATION));
            GestureDescription gestureDescription = gestureBuilder.build();
            Log.i(LatteService.TAG, "Execute Gesture " + gestureDescription.toString());
            LatteService.getInstance().dispatchGesture(gestureDescription, callback, null);
        }, 10);
        return false;
    }

    public void clearHistory(){
        orderedVisitiedWidgets.clear();
        visitedWidgets.clear();
        String fileName = FINISH_NAVIGATION_FILE_PATH;
        String dir = LatteService.getInstance().getBaseContext().getFilesDir().getPath();
        File file = new File(dir, fileName);
        file.delete();
    }

    public AccessibilityNodeInfo nextFocus(Navigator.DoneCallback callback) {
        WidgetInfo widgetInfo = ActualWidgetInfo.createFromA11yNode(LatteService.getInstance().getFocusedNode());
        if(visitedWidgets.contains(widgetInfo)){
            if(!widgetInfo.equals(orderedVisitiedWidgets.get(orderedVisitiedWidgets.size()-1))) {
                new Handler().post(() -> {
                    Log.i(LatteService.TAG, String.format("Widget %s is ALREADY visited XPath: %s.", widgetInfo, widgetInfo.getAttr("xpath")));
                    StringBuilder stringBuilder = new StringBuilder();
                    for(WidgetInfo wi : orderedVisitiedWidgets)
                        stringBuilder.append(wi + " $$$ " + (wi != null ? wi.getXpath() : "NONE") + "\n");
                    createFile(FINISH_NAVIGATION_FILE_PATH, stringBuilder.toString());
                    createFile(FINISH_ACTION_FILE_PATH, "DONE\n");
                    if (callback != null)
                        callback.onError("ALREADY_VISITED");
                });
                return null;
            }
            orderedVisitiedWidgets.add(new ActualWidgetInfo(
                    widgetInfo.getAttr("resourceId")+"_COPY",
                    widgetInfo.getAttr("contentDescription")+"_COPY",
                    widgetInfo.getAttr("text")+"_COPY",
                    widgetInfo.getAttr("class")+"_COPY",
                    LatteService.getInstance().getFocusedNode()
                    ));
        }
        else {
            visitedWidgets.add(widgetInfo);
            orderedVisitiedWidgets.add(widgetInfo);
        }
        Log.i(LatteService.TAG, String.format("Widget %s is visited XPATH: %s.", widgetInfo, widgetInfo != null ? widgetInfo.getAttr("xpath") : "NONE"));
        performNext(new Navigator.DoneCallback() {
            @Override
            public void onCompleted(AccessibilityNodeInfo nodeInfo) {
                WidgetInfo newWidgetNodeInfo = ActualWidgetInfo.createFromA11yNode(nodeInfo);
                Log.i(LatteService.TAG, "The next focused node is: " + newWidgetNodeInfo + " Xpath: " + newWidgetNodeInfo.getXpath());
                deleteFile(FINISH_ACTION_FILE_PATH);
                String jsonCommand;
                try {
                     jsonCommand = new JSONObject()
                            .put("resourceId", newWidgetNodeInfo.getAttr("resourceId"))
                            .put("contentDescription", newWidgetNodeInfo.getAttr("contentDescription"))
                            .put("text", newWidgetNodeInfo.getAttr("text"))
                            .put("class", newWidgetNodeInfo.getAttr("class"))
                            .put("xpath", newWidgetNodeInfo.getAttr("xpath"))
                            .put("located_by", "xpath")
                            .put("skip", false)
                            .put("action", "click")
                            .toString();

                } catch (JSONException e) {
                    e.printStackTrace();
                    jsonCommand = "error in json";
                }
                createFile(FINISH_ACTION_FILE_PATH, jsonCommand);
//                createFile(FINISH_ACTION_FILE_PATH, String.format("Next is done $ %s $%s\n", newWidgetNodeInfo, newWidgetNodeInfo.getXpath()));
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
        return null;
    }

    public AccessibilityNodeInfo selectFocus(Navigator.DoneCallback callback) {
        AccessibilityNodeInfo focusedNode = LatteService.getInstance().getFocusedNode();
        ActionUtils.performDoubleTap(new AccessibilityService.GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription gestureDescription) {
                WidgetInfo newWidgetNodeInfo = ActualWidgetInfo.createFromA11yNode(focusedNode);
                Log.i(LatteService.TAG, "The focused node is tapped: " + focusedNode);
                deleteFile(FINISH_ACTION_FILE_PATH);
                createFile(FINISH_ACTION_FILE_PATH, String.format("Select is done $ %s $%s\n", newWidgetNodeInfo, newWidgetNodeInfo.getXpath()));
            }

            @Override
            public void onCancelled(GestureDescription gestureDescription) {
                Log.i(LatteService.TAG, "Cancel in double tapping!");
            }
        });
        return null;
    }

    private void deleteFile(String fileName){
        String dir = LatteService.getInstance().getBaseContext().getFilesDir().getPath();
        File file = new File(dir, fileName);
        file.delete();
    }

    private void createFile(String fileName, String message){
        String dir = LatteService.getInstance().getBaseContext().getFilesDir().getPath();

        File file = new File(dir, fileName);
        Log.i(LatteService.TAG, "Output Path: " + file.getAbsolutePath());
        FileWriter myWriter = null;
        try {
            myWriter = new FileWriter(file);
            myWriter.write(message);
            myWriter.close();
        } catch (IOException ex) {
            ex.printStackTrace();
            Log.e(LatteService.TAG + "_RESULT", "Error: " + ex.getMessage());
        }
    }
}
