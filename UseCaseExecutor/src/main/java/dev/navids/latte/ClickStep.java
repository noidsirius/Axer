package dev.navids.latte;

import android.util.Log;

import org.json.simple.JSONObject;

public class ClickStep extends LocatableStep {
    ClickStep(JSONObject stepJson) {
        super(stepJson);
        Log.i(LatteService.TAG, "Clickable Step: " + this.getTargetWidgetInfo());
    }
    public static boolean isClickStep(String action){
        return action.equals("click");
    }


    @Override
    public String toString() {
        return String.format("ClickStep{State=%s,WidgetTarget=%s}", getState(), getTargetWidgetInfo());
    }
}
