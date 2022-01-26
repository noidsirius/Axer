package dev.navids.latte;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.graphics.Rect;
import android.os.Bundle;
import android.util.Log;
import android.util.Pair;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.ArrayList;
import java.util.List;

public class ActionUtils {
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
}
