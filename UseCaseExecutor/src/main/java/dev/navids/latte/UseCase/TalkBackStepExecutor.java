package dev.navids.latte.UseCase;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.os.Handler;
import android.util.Log;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

import dev.navids.latte.ActionUtils;
import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.LatteService;
import dev.navids.latte.Utils;
import dev.navids.latte.WidgetInfo;

public class TalkBackStepExecutor implements StepExecutor {
    private Map<Integer, String> pendingActions = new HashMap<>(); // TODO: It's buggy
    private int waitAttemptsForFocusChange = 0;
    private final int MAX_WAIT_FOR_FOCUS_CHANGE = 3; // TODO: Configurable
    private final int MAX_WAIT_FOR_FOCUS_CHANGE_AFTER_PERFORM_NEXT = MAX_WAIT_FOR_FOCUS_CHANGE + 2; // TODO: Configurable
    private final int MAX_VISITED_WIDGET = 4; // TODO: Configurable
    private final long GESTURE_DURATION = 400; // TODO: Configuratble
    public int pendingActionId = 0;
    private List<String> maskedAttributes = Collections.emptyList();//Arrays.asList("resourceId", "xpath"); // TODO: Configurable
    private Map<StepCommand, Map<WidgetInfo, Integer>> a11yNodeInfoTracker = new HashMap<>();
    @Override
    public boolean executeStep(StepCommand step) {
        Log.i(LatteService.TAG, "TB Executing Step " + step);
        if(step.getState() != StepState.RUNNING)
            return false;
        if(!step.shouldExecuteByA11yAssistantService())
            return LatteService.getInstance().getStepExecutor("regular").executeStep(step);
        if(pendingActions.size() > 0){
            Log.i(LatteService.TAG, String.format("Do nothing since we're another action is pending! (Size:%d)", pendingActions.size()));
            return false;
        }
        if(step instanceof LocatableStep) {
            LocatableStep locatableStep = (LocatableStep) step;
            if (LatteService.getInstance().getFocusedNode() == null) {
                waitAttemptsForFocusChange++;
                handleNullFocusNode(step);
                return false;
            }
            waitAttemptsForFocusChange = 0;
            if(checkStoppingCriteria(step, locatableStep)){
                Log.i(LatteService.TAG, "Reached Stopping Criteria!");
                return executeByRegularExecutor(step, locatableStep);
            }
            // ------------ TODO: Need major refactor -----------------
            List<AccessibilityNodeInfo> matchedNodes = Utils.findSimilarNodes(locatableStep.getTargetWidgetInfo());
            if(matchedNodes.size() != 1){ // TODO: Configurable, maybe we can tolerate multiple widgets with same info
                Log.i(LatteService.TAG, "The target widget is not unique. " + matchedNodes.size());
                locatableStep.setState(StepState.FAILED);
                return false;
            }
            // matchedNodes.get(0) is our target
            List<AccessibilityNodeInfo> similarNodes = Utils.findSimilarNodes(locatableStep.getTargetWidgetInfo(), maskedAttributes);
            if(!ActionUtils.isFocusedNodeTarget(similarNodes)){
                Log.i(LatteService.TAG, "Continue exploration!");
//                performNext(null);
                performNext();
                return false;
            }
            // Because isFocusedNodeTarget(similarNodes) == true, the focusedNode represent similarNodes.get(0)
            if(!similarNodes.get(0).equals(matchedNodes.get(0))){
                Log.i(LatteService.TAG, "The located widget is not correct, use regular executor");
                return executeByRegularExecutor(step, locatableStep);
            }
            locatableStep.setActedWidget(ActualWidgetInfo.createFromA11yNode(LatteService.getInstance().getFocusedNode()));
            if(locatableStep instanceof ClickStep){
                ActionUtils.performDoubleTap();
                locatableStep.setState(StepState.COMPLETED);
            }
            else if(locatableStep instanceof TypeStep){
                ActionUtils.performType(LatteService.getInstance().getFocusedNode(), ((TypeStep) locatableStep).getText());
                locatableStep.setState(StepState.COMPLETED);
            }
            else{
                Log.e(LatteService.TAG, "This locatable step is unrecognizable " + locatableStep);
                locatableStep.setState(StepState.FAILED);
                return false;
            }
            return true;
        }
        else{
            Log.e(LatteService.TAG, "This step is unrecognizable " + step);
            step.setState(StepState.FAILED);
            return false;
        }
    }

    @Override
    public boolean interrupt() {
        pendingActions.clear();
        return false;
    }

    public static boolean executeByRegularExecutor(StepCommand step, LocatableStep locatableStep) {
        LatteService.getInstance().getStepExecutor("regular").executeStep(step);
        if(step.getState() == StepState.COMPLETED) {
            locatableStep.setState(StepState.COMPLETED_BY_HELP);
            return true;
        }
        locatableStep.setState(StepState.FAILED);
        return false;
    }

    private boolean checkStoppingCriteria(StepCommand step, LocatableStep locatableStep) {
        if(!a11yNodeInfoTracker.containsKey(step))
            a11yNodeInfoTracker.put(step, new HashMap<>());
        WidgetInfo focusedNodeWI = ActualWidgetInfo.createFromA11yNode(LatteService.getInstance().getFocusedNode());
        a11yNodeInfoTracker.get(step).put(focusedNodeWI,a11yNodeInfoTracker.get(step).getOrDefault(focusedNodeWI, 0)+1);
        locatableStep.increaseActingAttempts();
        Log.i(LatteService.TAG, String.format("Widget %s is visited %d times", focusedNodeWI, a11yNodeInfoTracker.get(step).get(focusedNodeWI)));
        return locatableStep.reachedMaxActingAttempts() || a11yNodeInfoTracker.get(step).get(focusedNodeWI) > MAX_VISITED_WIDGET;
    }

    private void handleNullFocusNode(StepCommand step) {
        if (waitAttemptsForFocusChange < MAX_WAIT_FOR_FOCUS_CHANGE) {
            Log.i(LatteService.TAG, "Do nothing since no node is focused for " + waitAttemptsForFocusChange + " attempts.");
        }
        else if (waitAttemptsForFocusChange == MAX_WAIT_FOR_FOCUS_CHANGE) {
            Log.i(LatteService.TAG, "Perform next to refocus!");
            performNext();
        }
        else if (waitAttemptsForFocusChange < MAX_WAIT_FOR_FOCUS_CHANGE_AFTER_PERFORM_NEXT) {
            Log.i(LatteService.TAG, "Do nothing since no node is focused for " + waitAttemptsForFocusChange + " attempts. (After performing next)");
        }
        else {
            Log.i(LatteService.TAG, "Reached MAX_WAIT_FOR_FOCUS_CHANGE_AFTER_PERFORM_NEXT");
            step.setState(StepState.FAILED);
        }
    }

    // TODO: Do we need callback?
    public boolean performNext(){
        Log.i(LatteService.TAG, "performNext");
        final int thisActionId = pendingActionId;
        pendingActionId++;
        pendingActions.put(thisActionId, "Pending: I'm going to do NEXT");
        AccessibilityService.GestureResultCallback callback = new AccessibilityService.GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription gestureDescription) {
                pendingActions.remove(thisActionId);
            }

            @Override
            public void onCancelled(GestureDescription gestureDescription) {
                Log.i(LatteService.TAG, "Gesture is cancelled!");
                pendingActions.remove(thisActionId);
            }
        };

        new Handler().postDelayed(() -> {
            GestureDescription.Builder gestureBuilder = new GestureDescription.Builder();
            Path swipePath = new Path();
            Random random = new Random();
            int BASE = 5;
            int dx1 = random.nextInt(2 * BASE) - BASE;
            int dx2 = random.nextInt(2 * BASE) - BASE;
            int dy1 = random.nextInt(2 * BASE) - BASE;
            int dy2 = random.nextInt(2 * BASE) - BASE;
            int x1 = 50 + dx1;
            int x2 = 500 + dx2;
            int y1 = 500 + dy1;
            int y2 = 600 + dy2;
            swipePath.moveTo(x1, y1);
            swipePath.lineTo(x2, y2);
            gestureBuilder.addStroke(new GestureDescription.StrokeDescription(swipePath, 0, GESTURE_DURATION));
            GestureDescription gestureDescription = gestureBuilder.build();
            Log.i(LatteService.TAG, "Execute Gesture " + gestureDescription.toString());
            LatteService.getInstance().dispatchGesture(gestureDescription, callback, null);
        }, 10);
        return false;
    }
}
