package dev.navids.latte.UseCase;

import android.os.Bundle;
import android.util.Log;
import android.util.Pair;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.List;

import dev.navids.latte.ActionUtils;
import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.LatteService;
import dev.navids.latte.Utils;

public class RegularStepExecutor implements StepExecutor {

    public static boolean is_physical = false;

    @Override
    public boolean executeStep(StepCommand step) {
        Log.i(LatteService.TAG, "Reg Executing Step " + step + " Physical Touch: " + is_physical);
        if(step.getState() != StepState.RUNNING)
            return false;
        if(step instanceof LocatableStep){
            LocatableStep locatableStep = (LocatableStep) step;
            locatableStep.increaseLocatingAttempts();
            List<AccessibilityNodeInfo> similarNodes = Utils.findSimilarNodes(locatableStep.getTargetWidgetInfo());
            if(similarNodes.size() != 1){
                if(similarNodes.size() == 0) {
                    Log.i(LatteService.TAG, "The target widget could not be found in current screen.");
                    Log.i(LatteService.TAG, "The target XPATH: " + locatableStep.getTargetWidgetInfo().getXpath());
                    List<AccessibilityNodeInfo> allNodes = Utils.getAllA11yNodeInfo(false);
                    for(AccessibilityNodeInfo nodeInfo : allNodes){
                        ActualWidgetInfo actualWidgetInfo = ActualWidgetInfo.createFromA11yNode(nodeInfo);
                        if (actualWidgetInfo != null)
                            Log.i(LatteService.TAG, "\t" + actualWidgetInfo.getXpath());
                    }
                }
                else{
                    Log.i(LatteService.TAG, "There are more than one candidates for the target.");
                    for(AccessibilityNodeInfo node : similarNodes){
                        Log.i(LatteService.TAG, " Node: " + node);
                    }
                }
                if(locatableStep.reachedMaxLocatingAttempts()) {
                    locatableStep.setState(StepState.FAILED);
                    return false;
                }
                return true;
            }
            else {
                AccessibilityNodeInfo node = similarNodes.get(0);
                locatableStep.increaseActingAttempts();
                ActualWidgetInfo currentNodeInfo = ActualWidgetInfo.createFromA11yNode(node);
                locatableStep.setActedWidget(currentNodeInfo);
                if(locatableStep instanceof ClickStep)
                    return executeClick((ClickStep) locatableStep, node);
                else if(locatableStep instanceof TypeStep)
                    return executeType((TypeStep) locatableStep, node);
                else if(locatableStep instanceof FocusStep)
                    return executeFocus((FocusStep) locatableStep, node);
                else {
                    Log.e(LatteService.TAG, "This locatable step is unrecognizable " + locatableStep);
                    locatableStep.setState(StepState.FAILED);
                    return false;
                }
            }
        }
        else {
            Log.e(LatteService.TAG, "This step is unrecognizable " + step);
            step.setState(StepState.FAILED);
            return false;
        }
    }

    @Override
    public boolean interrupt() {
        // TODO
        return false;
    }

    private boolean executeClick(ClickStep clickStep, AccessibilityNodeInfo node){
        if(is_physical){
            Pair<Integer, Integer> clickableCoordinate = ActionUtils.getClickableCoordinate(node, false);
            int x =clickableCoordinate.first, y = clickableCoordinate.second;
            Log.e(LatteService.TAG, String.format("Physically clicking on (%d, %d)", x, y));
            boolean clickResult = ActionUtils.performTap(x, y);
            if(!clickResult){
                Log.e(LatteService.TAG, "The location could not be clicked.");
                clickStep.setState(StepState.FAILED);
                return false;
            }
            clickStep.setState(StepState.COMPLETED);
            return true;
        }
        else{
            AccessibilityNodeInfo clickableNode = node;
            while (clickableNode != null && !clickableNode.isClickable())
                clickableNode = clickableNode.getParent();
            if (clickableNode == null || !clickableNode.isClickable()) {
                Log.e(LatteService.TAG, "The widget is not clickable.");
                clickStep.setState(StepState.FAILED);
                return false;
            }
            ActualWidgetInfo clickableWidget = ActualWidgetInfo.createFromA11yNode(clickableNode);
            boolean result = clickableNode.performAction(AccessibilityNodeInfo.ACTION_CLICK);
            Log.i(LatteService.TAG, "Clicking on widget: " + clickableWidget.completeToString(true));
            clickStep.setState(result ? StepState.COMPLETED : StepState.FAILED);
            return result;
        }
    }

    private boolean executeFocus(FocusStep focusStep, AccessibilityNodeInfo node){
        boolean result = ActionUtils.a11yFocusOnNode(node);
        focusStep.setState(result ? StepState.COMPLETED : StepState.FAILED);
        return result;
    }

    private boolean executeType(TypeStep typeStep, AccessibilityNodeInfo node){
        Bundle arguments = new Bundle();
        arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, typeStep.getText());
        boolean result = node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments);
        typeStep.setState(result ? StepState.COMPLETED : StepState.FAILED);
        return result;
    }
}
