package dev.navids.latte.app;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.os.Bundle;
import android.util.Log;
import android.view.accessibility.AccessibilityNodeInfo;

public class TalkBackUtils {

    public static final int tapDuration = 100;
    private static AccessibilityService.GestureResultCallback defaultCallBack= new AccessibilityService.GestureResultCallback() {
        @Override
        public void onCompleted(GestureDescription gestureDescription) {
            Log.i(MyLatteService.TAG, "Complete Gesture " + gestureDescription.toString());
            super.onCompleted(gestureDescription);
        }

        @Override
        public void onCancelled(GestureDescription gestureDescription) {
            Log.i(MyLatteService.TAG, "Cancel Gesture " + gestureDescription.toString());
            super.onCancelled(gestureDescription);
        }
    };

    public static boolean performTap(int x, int y){ return performTap(x, y, tapDuration); }
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
        Log.i(MyLatteService.TAG, "Execute Gesture " + gestureDescription.toString());
        return MyLatteService.getInstance().dispatchGesture(gestureDescription, callback, null);
    }

    public static boolean performType(AccessibilityNodeInfo node, String message){
        Log.i(MyLatteService.TAG, "performType");
        Bundle arguments = new Bundle();
        arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, message);
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments);
    }


    public static boolean performDoubleTap(){
        Log.i(MyLatteService.TAG, "performDoubleTap");
        try {
            Thread.sleep(300); // TODO
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
        return performDoubleTap(0, 0); }
    public static boolean performDoubleTap(int x, int y){ return performDoubleTap(x, y, tapDuration); }
    public static boolean performDoubleTap(int x, int y, int duration){ return performDoubleTap(x, y, 0, duration); }
    public static boolean performDoubleTap(int x, int y, int startTime, int duration){ return performDoubleTap(x, y, startTime, duration, defaultCallBack); }
    public static boolean performDoubleTap(final int x, final int y, final int startTime, final int duration, final AccessibilityService.GestureResultCallback callback){
        AccessibilityService.GestureResultCallback newClickCallBack = new AccessibilityService.GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription gestureDescription) {
                Log.i(MyLatteService.TAG, "Complete Gesture " + gestureDescription.getStrokeCount());
                super.onCompleted(gestureDescription);
                try {
                    Thread.sleep(100); // TODO
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
                performTap(x, y, startTime, duration, callback);
            }

            @Override
            public void onCancelled(GestureDescription gestureDescription) {
                Log.i(MyLatteService.TAG, "Cancel Gesture");
                super.onCancelled(gestureDescription);
            }
        };
        return performTap(x, y, startTime, duration, newClickCallBack);
    }
}
