package dev.navids.latte;

import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.accessibility.AccessibilityNodeInfo;

import androidx.annotation.RequiresApi;

import java.util.List;

@RequiresApi(api = Build.VERSION_CODES.N)
public class RegularStepExecutor implements StepExecutor {
    @Override
    public boolean executeStep(StepCommand step) {
        Log.i(LatteService.TAG, "Executing Step " + step);
        if(step.getState() != StepCommand.StepState.RUNNING)
            return false;
        if(step instanceof LocatableStep){
            LocatableStep locatableStep = (LocatableStep) step;
            locatableStep.increaseLocatingAttempts();
            List<AccessibilityNodeInfo> similarNodes = Utils.findSimilarNodes(locatableStep.getTargetWidgetInfo());
            if(similarNodes.size() != 1){
                if(similarNodes.size() == 0)
                    Log.i(LatteService.TAG, "The target widget could not be found in current screen.");
                else{
                    Log.i(LatteService.TAG, "There are more than one candidates for the target.");
                    for(AccessibilityNodeInfo node : similarNodes){
                        Log.i(LatteService.TAG, " Node: " + node);
                    }
                }
                if(locatableStep.reachedMaxLocatingAttempts()) {
                    locatableStep.setState(StepCommand.StepState.FAILED);
                    return false;
                }
                return true;
            }
            else {
                AccessibilityNodeInfo node = similarNodes.get(0);
                locatableStep.increaseActingAttempts();
                ActualWidgetInfo currentNodeInfo = ActualWidgetInfo.createFromA11yNode(node);
                if(locatableStep instanceof ClickStep)
                    return executeClick((ClickStep) locatableStep, node);
                else if(locatableStep instanceof TypeStep)
                    return executeType((TypeStep) locatableStep, node);
                else {
                    Log.e(LatteService.TAG, "This locatable step is unrecognizable " + locatableStep);
                    locatableStep.setState(StepCommand.StepState.FAILED);
                    return false;
                }
            }
        }
        else {
            Log.e(LatteService.TAG, "This step is unrecognizable " + step);
            step.setState(StepCommand.StepState.FAILED);
            return false;
        }
    }

    private boolean executeClick(ClickStep clickStep, AccessibilityNodeInfo node){
        AccessibilityNodeInfo clickableNode = node;
        while (clickableNode != null && !clickableNode.isClickable())
            clickableNode = clickableNode.getParent();
        if (clickableNode == null || !clickableNode.isClickable()) {
            Log.e(LatteService.TAG, "The widget is not clickable.");
            clickStep.setState(StepCommand.StepState.FAILED);
            return false;
        }
        clickableNode.performAction(AccessibilityNodeInfo.ACTION_CLICK);
        clickStep.setState(StepCommand.StepState.COMPLETED);
        return true;
    }

    private boolean executeType(TypeStep typeStep, AccessibilityNodeInfo node){
        Bundle arguments = new Bundle();
        arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, typeStep.getText());
        boolean result = node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments);
        typeStep.setState(result ? StepCommand.StepState.COMPLETED : StepCommand.StepState.FAILED);
        return result;
    }
}
