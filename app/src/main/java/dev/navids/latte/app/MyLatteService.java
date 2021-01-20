package dev.navids.latte.app;

import android.view.accessibility.AccessibilityEvent;

import dev.navids.latte.LatteService;

public class MyLatteService extends LatteService {
    static String TAG = "LATTE_SERVICE_APP";
    public MyLatteService() {
    }
    TalkBackStepExecutor talkBackStepExecutor = new TalkBackStepExecutor();
    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        addStepExecutor("talkback", talkBackStepExecutor);
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        super.onAccessibilityEvent(event);
        if(event.getEventType() == AccessibilityEvent.TYPE_VIEW_ACCESSIBILITY_FOCUSED)
            talkBackStepExecutor.setFocusedNode(event.getSource());
    }
}
