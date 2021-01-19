package dev.navids.latte;

import android.accessibilityservice.AccessibilityService;
import android.content.IntentFilter;
import android.os.Build;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;

import androidx.annotation.RequiresApi;

import java.util.HashMap;
import java.util.Map;

public class LatteService extends AccessibilityService {
    private static LatteService instance;
    CommandReceiver receiver;
    public boolean isConnected() {
        return connected;
    }

    private boolean connected = false;
    static String TAG = "LATTE_SERVICE";

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

    @RequiresApi(api = Build.VERSION_CODES.N)
    public StepExecutor getStepExecutor(String key){
        return stepExecutorsMap.getOrDefault(key, null);
    }

    @RequiresApi(api = Build.VERSION_CODES.N)
    @Override
    protected void onServiceConnected() {
        Log.i(TAG, "Latte Service has started!");
        receiver = new CommandReceiver();
        registerReceiver(receiver, new IntentFilter(CommandReceiver.ACTION_COMMAND_INTENT));
        instance = this;
        connected = true;
        addStepExecutor("regular", new RegularStepExecutor());
        UseCaseExecutor.v().run();
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
        Log.i(TAG, "   Type : " +AccessibilityEvent.eventTypeToString(event.getEventType()));
    }

    @Override
    public void onInterrupt() {

    }
}
