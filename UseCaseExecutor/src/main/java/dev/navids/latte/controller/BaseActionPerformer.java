package dev.navids.latte.controller;

import android.os.Bundle;
import android.view.accessibility.AccessibilityNodeInfo;

import dev.navids.latte.ActionUtils;
import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.UseCase.ClickStep;
import dev.navids.latte.UseCase.FocusStep;
import dev.navids.latte.UseCase.NextStep;
import dev.navids.latte.UseCase.PreviousStep;
import dev.navids.latte.UseCase.TypeStep;

public class BaseActionPerformer extends AbstractActionPerformer {

    @Override
    public boolean executeClick(ClickStep clickStep, ActualWidgetInfo actualWidgetInfo) {
        return actualWidgetInfo.getA11yNodeInfo().performAction(AccessibilityNodeInfo.ACTION_CLICK);
    }

    @Override
    public boolean executeType(TypeStep typeStep, ActualWidgetInfo actualWidgetInfo) {
        Bundle arguments = new Bundle();
        arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, typeStep.getText());
        return actualWidgetInfo.getA11yNodeInfo().performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments);
    }

    @Override
    public boolean executeFocus(FocusStep focusStep, ActualWidgetInfo actualWidgetInfo) {
        return ActionUtils.focusOnNode(actualWidgetInfo.getA11yNodeInfo());
    }

    @Override
    public void navigateNext(NextStep nextStep, ExecutorCallback callback) {

    }

    @Override
    public void navigatePrevious(PreviousStep previousStep, ExecutorCallback callback) {

    }
}
