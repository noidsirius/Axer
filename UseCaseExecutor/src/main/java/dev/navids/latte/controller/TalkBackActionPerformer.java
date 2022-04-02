package dev.navids.latte.controller;

import android.util.Log;
import android.view.accessibility.AccessibilityNodeInfo;

import dev.navids.latte.ActionUtils;
import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.LatteService;
import dev.navids.latte.UseCase.ClickStep;
import dev.navids.latte.UseCase.FocusStep;
import dev.navids.latte.UseCase.NextStep;
import dev.navids.latte.UseCase.PreviousStep;
import dev.navids.latte.UseCase.TypeStep;

public class TalkBackActionPerformer extends BaseActionPerformer {
    static class TalkBackActionCallback implements ActionUtils.ActionCallback{
        private ExecutorCallback callback;
        TalkBackActionCallback(ExecutorCallback callback){
            this.callback = callback;
        }
        @Override
        public void onCompleted(AccessibilityNodeInfo nodeInfo) {
            callback.onCompleted(ActualWidgetInfo.createFromA11yNode(nodeInfo));
        }

        @Override
        public void onError(String message) {
            callback.onError(message);
        }
    }

    private boolean isNotFocused(ActualWidgetInfo actualWidgetInfo) {
        if(!ActionUtils.isFocusedNodeTarget(actualWidgetInfo.getA11yNodeInfo())){
            Log.e(LatteService.TAG, String.format("The focused node %s is different from target node %s", LatteService.getInstance().getAccessibilityFocusedNode(), actualWidgetInfo));
            return true;
        }
        return false;
    }

    @Override
    public boolean executeClick(ClickStep clickStep, ActualWidgetInfo actualWidgetInfo) {
        if (isNotFocused(actualWidgetInfo))
            return false;
        return ActionUtils.performDoubleTap();
    }

    @Override
    public boolean executeType(TypeStep typeStep, ActualWidgetInfo actualWidgetInfo) {
        if (isNotFocused(actualWidgetInfo))
            return false;
        return super.executeType(typeStep, actualWidgetInfo);
    }

    @Override
    public boolean executeFocus(FocusStep focusStep, ActualWidgetInfo actualWidgetInfo) {
        if (isNotFocused(actualWidgetInfo))
            return false;
        return super.executeFocus(focusStep, actualWidgetInfo);
    }

    @Override
    public void navigateNext(NextStep nextStep, ExecutorCallback callback) {
        ActionUtils.swipeRight(new TalkBackActionCallback(callback));
    }

    @Override
    public void navigatePrevious(PreviousStep previousStep, ExecutorCallback callback) {
        ActionUtils.swipeLeft(new TalkBackActionCallback(callback));
    }
}
