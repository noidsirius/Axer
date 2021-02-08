package dev.navids.latte;

import android.view.accessibility.AccessibilityNodeInfo;

public interface Navigator {
    interface DoneCallback{
        void onCompleted(AccessibilityNodeInfo nodeInfo);
        void onError(String message);
    };
    public AccessibilityNodeInfo nextFocus(DoneCallback callback);
    public AccessibilityNodeInfo selectFocus(DoneCallback callback);
    public boolean click(AccessibilityNodeInfo node, DoneCallback callback);
    public AccessibilityNodeInfo locate(AccessibilityNodeInfo node, DoneCallback callback);
}
