package dev.navids.latte;

import android.view.accessibility.AccessibilityNodeInfo;

public class RegularNavigator implements Navigator {
    @Override
    public AccessibilityNodeInfo nextFocus(DoneCallback callback) {
        return null;
    }

    @Override
    public AccessibilityNodeInfo selectFocus(DoneCallback callback) {
        return null;
    }

    @Override
    public boolean click(AccessibilityNodeInfo node, DoneCallback callback) {
        return false;
    }

    @Override
    public AccessibilityNodeInfo locate(AccessibilityNodeInfo node, DoneCallback callback) {
        return null;
    }
}