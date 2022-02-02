package dev.navids.latte;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.Context;
import android.graphics.Path;
import android.graphics.Point;
import android.graphics.Rect;
import android.os.Bundle;
import android.os.Handler;
import android.util.Log;
import android.util.Pair;
import android.view.Display;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

public class ActionUtils {
    private static Map<Integer, String> pendingActions = new HashMap<>();
    private static int pendingActionId = 0;
    public static boolean isActionPending(){
        return pendingActions.size() > 0;
    }
    public static void interrupt(){
        pendingActions.clear(); // TODO: Do we need to cancel the pending actions somehow?
    }

    private static AccessibilityService.GestureResultCallback defaultCallBack= new AccessibilityService.GestureResultCallback() {
        @Override
        public void onCompleted(GestureDescription gestureDescription) {
            Log.i(LatteService.TAG, "Complete Gesture " + gestureDescription.toString());
            super.onCompleted(gestureDescription);
        }

        @Override
        public void onCancelled(GestureDescription gestureDescription) {
            Log.i(LatteService.TAG, "Cancel Gesture " + gestureDescription.toString());
            super.onCancelled(gestureDescription);
        }
    };

    public static boolean isFocusedNodeTarget(List<AccessibilityNodeInfo> similarNodes) {
        if(similarNodes.size() == 0)
            return false;
        AccessibilityNodeInfo targetNode = similarNodes.get(0); // TODO: This strategy works even we found multiple similar widgets
        AccessibilityNodeInfo firstReachableNode = targetNode;
        boolean isSimilar = firstReachableNode != null && firstReachableNode.equals(LatteService.getInstance().getFocusedNode());
        if(!isSimilar) {
            AccessibilityNodeInfo it = targetNode;
            while (it != null) {
                if (it.isClickable()) {
                    firstReachableNode = it;
                    break;
                }
                it = it.getParent();
            }
            Log.i(LatteService.TAG, "-- FIRST REACHABLE NODE IS " + firstReachableNode);
            isSimilar = firstReachableNode != null && firstReachableNode.equals(LatteService.getInstance().getFocusedNode());
        }
        return isSimilar;
    }

    public static Pair<Integer, Integer> getClickableCoordinate(AccessibilityNodeInfo node){
        return getClickableCoordinate(node, true);
    }

    public static Pair<Integer, Integer> getClickableCoordinate(AccessibilityNodeInfo node, boolean fast){
        int x, y;
        if(fast)
        {
            List<AccessibilityNodeInfo> children = new ArrayList<>();
            children.add(node);
            for (int i = 0; i < children.size(); i++) {
                AccessibilityNodeInfo child = children.get(i);
                for (int j = 0; j < child.getChildCount(); j++)
                    children.add(child.getChild(j));
            }
            Rect nodeBox = new Rect();
            node.getBoundsInScreen(nodeBox);
            children.remove(0);
            int left = nodeBox.right;
            int right = nodeBox.left;
            int top = nodeBox.bottom;
            int bottom = nodeBox.top;
            for (AccessibilityNodeInfo child : children) {
                if(!child.isClickable())
                    continue;
                Rect box = new Rect();
                child.getBoundsInScreen(box);
                left = Integer.min(left, box.left);
                right = Integer.max(right, box.right);
                top = Integer.min(top, box.top);
                bottom = Integer.max(bottom, box.bottom);
            }
            Log.i(LatteService.TAG, " -------> " + nodeBox + " " + left + " " + right + " " + top + " " + bottom);
            if(left > nodeBox.left)
                x = (left+ nodeBox.left) / 2;
            else if(right < nodeBox.right)
                x = (right + nodeBox.right) / 2;
            else
                x = nodeBox.centerX();
            if(top > nodeBox.top)
                y = (top+nodeBox.top) / 2;
            else if(bottom < nodeBox.bottom)
                y = (top+nodeBox.top) / 2;
            else
                y = nodeBox.centerY();
        }
        else {
            Rect box = new Rect();
            node.getBoundsInScreen(box);
            x = box.centerX();
            y = box.centerY();
        }
        return new Pair<>(x,y);
    }

    public static boolean performTap(int x, int y){ return performTap(x, y, Config.v().TAP_DURATION); }
    public static boolean performTap(int x, int y, int duration){ return performTap(x, y, 0, duration); }
    public static boolean performTap(int x, int y, int startTime, int duration){ return performTap(x, y, startTime, duration, defaultCallBack); }
    public static boolean performTap(int x, int y, int startTime, int duration, AccessibilityService.GestureResultCallback callback){
        if(x < 0 || y < 0)
            return false;
        GestureDescription.Builder gestureBuilder = new GestureDescription.Builder();
        Path swipePath = new Path();
        swipePath.moveTo(x, y);
        gestureBuilder.addStroke(new GestureDescription.StrokeDescription(swipePath, startTime, duration));
        GestureDescription gestureDescription = gestureBuilder.build();
        Log.i(LatteService.TAG, "Execute Gesture " + gestureDescription.toString());
        return LatteService.getInstance().dispatchGesture(gestureDescription, callback, null);
    }

    public static boolean performType(AccessibilityNodeInfo node, String message){
        Log.i(LatteService.TAG, "performType");
        Bundle arguments = new Bundle();
        arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, message);
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments);
    }

    public static boolean performDoubleTap(){
        return performDoubleTap(defaultCallBack);
    }
    public static boolean performDoubleTap(final AccessibilityService.GestureResultCallback callback){
        Log.i(LatteService.TAG, "performDoubleTap");
        try {
            Thread.sleep(300); // TODO: What is this?
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
        return performDoubleTap(0, 0, callback);
    }
    public static boolean performDoubleTap(int x, int y, final AccessibilityService.GestureResultCallback callback){ return performDoubleTap(x, y, Config.v().TAP_DURATION, callback); }
    public static boolean performDoubleTap(int x, int y, int duration, final AccessibilityService.GestureResultCallback callback){ return performDoubleTap(x, y, 0, duration, callback); }
    public static boolean performDoubleTap(final int x, final int y, final int startTime, final int duration, final AccessibilityService.GestureResultCallback callback){
        AccessibilityService.GestureResultCallback newClickCallBack = new AccessibilityService.GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription gestureDescription) {
                Log.i(LatteService.TAG, "Complete Gesture " + gestureDescription.getStrokeCount());
                super.onCompleted(gestureDescription);
                try {
                    Thread.sleep(Config.v().DOUBLE_TAP_BETWEEN_TIME);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
                performTap(x, y, startTime, duration, callback);
            }

            @Override
            public void onCancelled(GestureDescription gestureDescription) {
                Log.i(LatteService.TAG, "Cancel Gesture");
                super.onCancelled(gestureDescription);
                if(callback != null)
                    callback.onCancelled(gestureDescription);
            }
        };
        return performTap(x, y, startTime, duration, newClickCallBack);
    }

    private static void executeSwipeGesture(String direction, String secondDirection, AccessibilityService.GestureResultCallback callback){
        GestureDescription.Builder gestureBuilder = new GestureDescription.Builder();
        Path swipePath = new Path();
        Random random = new Random();
        int BASE = 5;
        int dx1 = random.nextInt(2 * BASE) - BASE;
        int dx2 = random.nextInt(2 * BASE) - BASE;
        int dy1 = random.nextInt(2 * BASE) - BASE;
        int dy2 = random.nextInt(2 * BASE) - BASE;
        int x1, x2, y1, y2;
        WindowManager wm = (WindowManager) LatteService.getInstance().getApplicationContext().getSystemService(Context.WINDOW_SERVICE);
        Display display = wm.getDefaultDisplay();
        Point size = new Point();
        display.getSize(size);
        int width = size.x;
        int height = size.y;
        x1 = width / 2 + dx1;
        y1 = height / 2 + dy1;
        // TODO: The const values need to be configured
        switch (direction) {
            case "right":
                x2 = width - 100 + dx2;
                y2 = y1 + dy2;
                break;
            case "left":
                x2 = 100 + dx2;
                y2 = y1 + dy2;
                break;
            case "up":
                x2 = x1 + dx1;
                y2 = 100 + dy2;
                break;
            case "down":
                x2 = x1 + dx1;
                y2 = height - 100 + dy2;
                break;
            default:
                Log.e(LatteService.TAG, "Incorrect direction " + direction);
                return;
        }

        swipePath.moveTo(x1, y1);
        swipePath.lineTo(x2, y2);
        if (!secondDirection.isEmpty())
        {
            // TODO: Generalize to all directions
            if (direction.equals("up") && secondDirection.equals("left"))
            {
                Log.i(LatteService.TAG, "Add left direction to " + Integer.toString(100+dx1) + " " +Integer.toString(y2-dy1));
                swipePath.lineTo(100+dx1, y2-dy1);
            }
        }
        gestureBuilder.addStroke(new GestureDescription.StrokeDescription(swipePath, 0, Config.v().GESTURE_DURATION));
        GestureDescription gestureDescription = gestureBuilder.build();
        Log.i(LatteService.TAG, "Execute Gesture " + gestureDescription.toString());
        LatteService.getInstance().dispatchGesture(gestureDescription, callback, null);
    }

    public static boolean swipeLeft(Navigator.DoneCallback doneCallback){ return swipeToDirection("left", doneCallback);}
    public static boolean swipeRight(Navigator.DoneCallback doneCallback){ return swipeToDirection("right", doneCallback);}
    public static boolean swipeUp(Navigator.DoneCallback doneCallback){ return swipeToDirection("up", doneCallback);}
    public static boolean swipeDown(Navigator.DoneCallback doneCallback){ return swipeToDirection("down", doneCallback);}
    public static boolean swipeToDirection(String direction, Navigator.DoneCallback doneCallback){
        return swipeToDirection(direction, "", doneCallback);
    }
    public static boolean swipeUpThenLeft(Navigator.DoneCallback doneCallback){
        return swipeToDirection("up", "left", doneCallback);
    }
    public static boolean swipeToDirection(String direction, String secondDirection, Navigator.DoneCallback doneCallback){
        if(isActionPending()){
            Log.i(LatteService.TAG, String.format("Do nothing since another action is pending! (Size:%d)", pendingActions.size()));
            return false;
        }
        final int thisActionId = pendingActionId;
        pendingActionId++;
        pendingActions.put(thisActionId, "Pending: I'm going to swipe " + direction);
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

        new Handler().postDelayed(() -> { executeSwipeGesture(direction, secondDirection, callback);}, 10);
        return true;
    }
}
