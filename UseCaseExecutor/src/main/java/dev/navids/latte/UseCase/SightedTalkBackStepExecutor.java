package dev.navids.latte.UseCase;

import android.util.Log;
import android.util.Pair;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.List;

import dev.navids.latte.ActionUtils;
import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.LatteService;
import dev.navids.latte.Utils;

public class SightedTalkBackStepExecutor implements StepExecutor {
    public static boolean apiFocus = false;
    @Override
    public boolean executeStep(StepCommand step) {
        Log.i(LatteService.TAG, "STB Executing Step " + step);
        if(step.getState() != StepState.RUNNING)
            return false;
        if(step instanceof LocatableStep){
            LocatableStep locatableStep = (LocatableStep) step;
            locatableStep.increaseLocatingAttempts();
            if(locatableStep.reachedMaxLocatingAttempts()){
                Log.i(LatteService.TAG, "Reached Stopping Criteria!");
                locatableStep.setState(StepState.FAILED);
                return false;
            }
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
                return true;
            }
            else {
                AccessibilityNodeInfo node = similarNodes.get(0);
                if(!ActionUtils.isFocusedNodeTarget(similarNodes)){
                    if(apiFocus){
                        Log.e(LatteService.TAG, String.format("API Focusing on %s", node));
                        ActionUtils.a11yFocusOnNode(node);
                    }
                    else {
                        Pair<Integer, Integer> clickableCoordinate = ActionUtils.getClickableCoordinate(node, false);
                        int x = clickableCoordinate.first, y = clickableCoordinate.second;
                        Log.e(LatteService.TAG, String.format("Physically clicking on (%d, %d)", x, y));
                        ActionUtils.performTap(x, y);
                    }
                    locatableStep.increaseLocatingAttempts();
                    return false;
                }
                locatableStep.increaseActingAttempts();
                locatableStep.setActedWidget(ActualWidgetInfo.createFromA11yNode(LatteService.getInstance().getAccessibilityFocusedNode()));
                if(locatableStep instanceof ClickStep){
                    ActionUtils.performDoubleTap();
                    locatableStep.setState(StepState.COMPLETED);
                }
                else if(locatableStep instanceof TypeStep){
                    ActionUtils.performType(LatteService.getInstance().getAccessibilityFocusedNode(), ((TypeStep) locatableStep).getText());
                    locatableStep.setState(StepState.COMPLETED);
                }
                else{
                    Log.e(LatteService.TAG, "This locatable step is unrecognizable " + locatableStep);
                    locatableStep.setState(StepState.FAILED);
                    return false;
                }
                return true;
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
}
