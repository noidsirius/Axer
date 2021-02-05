package dev.navids.latte;

import org.json.simple.JSONObject;

public abstract class LocatableStep extends StepCommand {
    private ConceivedWidgetInfo targetWidget;

    public int getNumberOfLocatingAttempts() {
        return numberOfLocatingAttempts;
    }

    int numberOfLocatingAttempts = 0;
    public final static int MAX_LOCATING_ATTEMPT = 4; // TODO: configurable

    public void increaseLocatingAttempts(){
        numberOfLocatingAttempts += 1;
    }

    public boolean reachedMaxLocatingAttempts(){
        return numberOfLocatingAttempts >= MAX_LOCATING_ATTEMPT;
    }

    int numberOfActingAttempts = 0;
    public final static int MAX_ACTING_ATTEMPT = 50; // TODO: configurable

    public void increaseActingAttempts(){
        numberOfActingAttempts += 1;
    }

    public boolean reachedMaxActingAttempts(){
        return numberOfActingAttempts >= MAX_ACTING_ATTEMPT;
    }

    LocatableStep(JSONObject stepJson) {
        super(stepJson);
        targetWidget = ConceivedWidgetInfo.createFromJson(stepJson);
    }

    public static boolean isLocatableAction(String action){
        return action.equals("click") || action.equals("send_keys");
    }

    public ConceivedWidgetInfo getTargetWidgetInfo() {
        return targetWidget;
    }

}