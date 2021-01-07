package dev.navids.latte.usecaseexecutor;

import android.accessibilityservice.AccessibilityService;
import android.app.Service;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Handler;
import android.os.IBinder;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;

public class LatteService extends AccessibilityService {
    private static LatteService instance;

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

    @Override
    protected void onServiceConnected() {
        Log.i(TAG, "I'm in the service 2");
        instance = this;
        connected = true;
    }

    @Override
    public void onDestroy() {
        connected = false;
        super.onDestroy();
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if(event == null){
            Log.i(TAG, "Event NULL");
            return;
        }
        Log.i(TAG, "   Type : " +AccessibilityEvent.eventTypeToString(event.getEventType()));
    }

    @Override
    public void onInterrupt() {

    }
}
