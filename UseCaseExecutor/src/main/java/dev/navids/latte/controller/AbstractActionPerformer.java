package dev.navids.latte.controller;

import android.util.Log;
import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.LatteService;
import dev.navids.latte.UseCase.ClickStep;
import dev.navids.latte.UseCase.FocusStep;
import dev.navids.latte.UseCase.LocatableStep;
import dev.navids.latte.UseCase.NavigateStep;
import dev.navids.latte.UseCase.NextStep;
import dev.navids.latte.UseCase.PreviousStep;
import dev.navids.latte.UseCase.TypeStep;

public abstract class AbstractActionPerformer implements ActionPerformer {
    @Override
    public void navigate(NavigateStep navigateStep, ExecutorCallback callback) {
        if(callback == null)
            callback = new DummyExecutorCallback();
        if (navigateStep instanceof NextStep)
            navigateNext((NextStep) navigateStep, callback);
        else if (navigateStep instanceof PreviousStep)
            navigatePrevious((PreviousStep) navigateStep, callback);
        else {
            Log.e(LatteService.TAG, "This navigate step is unrecognizable " + navigateStep);
            callback.onError("Unrecognizable Action");
        }
    }

    @Override
    public final void execute(LocatableStep locatableStep, ActualWidgetInfo actualWidgetInfo, ExecutorCallback callback) {
        if(callback == null)
            callback = new DummyExecutorCallback();
        Log.i(LatteService.TAG, this.getClass().getSimpleName() + " executing " + locatableStep);
        boolean actionResult = false;
        if (locatableStep == null || actualWidgetInfo == null){
            Log.e(LatteService.TAG, String.format("Problem with locatable step %s or actualWidgetInfo %s", locatableStep, actualWidgetInfo));
            callback.onError("Error in parameters");
            return;
        }
        if(locatableStep instanceof ClickStep) {
            actionResult = executeClick((ClickStep) locatableStep, actualWidgetInfo);
        }
        else if(locatableStep instanceof TypeStep) {
            actionResult = executeType((TypeStep) locatableStep, actualWidgetInfo);
        }
        else if(locatableStep instanceof FocusStep){
            actionResult = executeFocus((FocusStep) locatableStep, actualWidgetInfo);
        }
        else {
            Log.e(LatteService.TAG, "This locatable step is unrecognizable " + locatableStep);
            callback.onError("Unrecognizable Action");
            return;
        }
        if(actionResult){
            Log.i(LatteService.TAG, "Action is executed successfully!");
            callback.onCompleted();
        }
        else{
            Log.i(LatteService.TAG, "Action could not be executed!");
            callback.onError("Error on execution!");
        }
    }

    public abstract boolean executeClick(ClickStep clickStep, ActualWidgetInfo actualWidgetInfo);
    public abstract boolean executeType(TypeStep typeStep, ActualWidgetInfo actualWidgetInfo);
    public abstract boolean executeFocus(FocusStep focusStep, ActualWidgetInfo actualWidgetInfo);
    public abstract void navigateNext(NextStep nextStep, ExecutorCallback callback);
    public abstract void navigatePrevious(PreviousStep previousStep, ExecutorCallback callback);
}
