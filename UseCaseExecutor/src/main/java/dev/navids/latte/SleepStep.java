package dev.navids.latte;

import android.util.Log;

import org.json.simple.JSONObject;

public class SleepStep extends StepCommand {
    private long sleepTime;

    SleepStep(JSONObject stepJson) {
        super(stepJson);
        long sleepTime = Long.parseLong((String) stepJson.getOrDefault("sleep", "-1"));
        if(sleepTime == -1) {
            Log.e(LatteService.TAG, "Issue with sleep step " + stepJson);
            sleepTime = 0;
        }
        this.sleepTime = sleepTime;
        Log.i(LatteService.TAG, "Sleep Step: " + this.sleepTime);
    }

    public static boolean isSleepAction(String action){
        return action.equals("sleep");
    }

    public long getSleepTime() {
        return sleepTime;
    }

    @Override
    public String toString() {
        return "SleepStep{" +
                "State=" + getState().name() +
                "sleepTime=" + sleepTime +
                '}';
    }
}
