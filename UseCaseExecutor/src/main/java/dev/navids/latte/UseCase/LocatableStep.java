package dev.navids.latte.UseCase;

import org.json.simple.JSONObject;

import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.ConceivedWidgetInfo;

public abstract class LocatableStep extends StepCommand {
    private ConceivedWidgetInfo targetWidget;

    public ActualWidgetInfo getActedWidget() {
        return actedWidget;
    }

    public void setActedWidget(ActualWidgetInfo actedWidget) {
        this.actedWidget = actedWidget;
    }

    private ActualWidgetInfo actedWidget = null;

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

    public int getNumberOfActingAttempts() {
        return numberOfActingAttempts;
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
