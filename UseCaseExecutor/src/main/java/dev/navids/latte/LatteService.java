package dev.navids.latte;

import android.accessibilityservice.AccessibilityService;
import android.content.IntentFilter;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;


import java.io.File;
import java.util.HashMap;
import java.util.Map;

import dev.navids.latte.UseCase.RegularStepExecutor;
import dev.navids.latte.UseCase.SightedTalkBackStepExecutor;
import dev.navids.latte.UseCase.StepExecutor;
import dev.navids.latte.UseCase.TalkBackStepExecutor;

public class LatteService extends AccessibilityService {
    private static LatteService instance;

    public AccessibilityNodeInfo getAccessibilityFocusedNode() {
        return accessibilityFocusedNode;
    }

    public AccessibilityNodeInfo getFocusedNode() {
        return focusedNode;
    }

    private AccessibilityNodeInfo focusedNode;
    private AccessibilityNodeInfo accessibilityFocusedNode;
    CommandReceiver receiver;
    public boolean isConnected() {
        return connected;
    }

    private boolean connected = false;
    public static String TAG = "LATTE_SERVICE";

    public static LatteService getInstance() {
        return instance;
    }
    public LatteService() {
    }

    private Map<String, StepExecutor> stepExecutorsMap = new HashMap<>();

    public boolean addStepExecutor(String key, StepExecutor stepExecutor){
        if(stepExecutorsMap.containsKey(key))
            return false;
        stepExecutorsMap.put(key, stepExecutor);
        return true;
    }

    public StepExecutor getStepExecutor(String key){
        return stepExecutorsMap.getOrDefault(key, null);
    }
    @Override
    protected void onServiceConnected() {
        Log.i(TAG, "Latte Service has started!");
        File dir = new File(getBaseContext().getFilesDir().getPath());
        for(File file : dir.listFiles())
            if(!file.isDirectory())
                file.delete();
        receiver = new CommandReceiver();
        registerReceiver(receiver, new IntentFilter(CommandReceiver.ACTION_COMMAND_INTENT));
        instance = this;
        connected = true;
        addStepExecutor("regular", new RegularStepExecutor());
        addStepExecutor("talkback", new TalkBackStepExecutor());
        addStepExecutor("sighted_tb", new SightedTalkBackStepExecutor());
    }

    @Override
    public void onDestroy() {
        connected = false;
        unregisterReceiver(receiver);
        super.onDestroy();
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if(event == null){
            Log.i(TAG, "Incomming event is null!");
            return;
        }
        if(event.getEventType() == AccessibilityEvent.TYPE_VIEW_ACCESSIBILITY_FOCUSED) {
            accessibilityFocusedNode = event.getSource();
        }
        else if(event.getEventType() == AccessibilityEvent.TYPE_VIEW_FOCUSED) {
            focusedNode = event.getSource();
        }
//        Log.i(TAG, "   Type : " +AccessibilityEvent.eventTypeToString(event.getEventType()));
    }

    @Override
    public void onInterrupt() {

    }
}
