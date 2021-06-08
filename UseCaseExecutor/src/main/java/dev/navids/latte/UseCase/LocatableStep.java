package dev.navids.latte.UseCase;

import org.json.simple.JSONObject;

import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.ConceivedWidgetInfo;
import dev.navids.latte.Config;

public abstract class LocatableStep extends StepCommand {
    private final ConceivedWidgetInfo targetWidget;

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

    public void increaseLocatingAttempts() {
        numberOfLocatingAttempts += 1;
    }

    public boolean reachedMaxLocatingAttempts() {
        return numberOfLocatingAttempts >= Config.v().MAX_LOCATING_ATTEMPT;
    }

    public int getNumberOfActingAttempts() {
        return numberOfActingAttempts;
    }

    int numberOfActingAttempts = 0;

    public void increaseActingAttempts() {
        numberOfActingAttempts += 1;
    }

    public boolean reachedMaxActingAttempts() {
        return numberOfActingAttempts >= Config.v().MAX_ACTING_ATTEMPT;
    }

    LocatableStep(JSONObject stepJson) {
        super(stepJson);
        targetWidget = ConceivedWidgetInfo.createFromJson(stepJson);
    }

    public static boolean isLocatableAction(String action) {
        return action.equals("click") || action.equals("send_keys");
    }

    public ConceivedWidgetInfo getTargetWidgetInfo() {
        return targetWidget;
    }

}
