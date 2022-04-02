package dev.navids.latte.controller;

import android.os.Handler;
import android.util.Log;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.ConceivedWidgetInfo;
import dev.navids.latte.LatteService;
import dev.navids.latte.UseCase.LocatableStep;
import dev.navids.latte.Utils;

public abstract class AbstractLocator implements Locator {
    enum LocatorStatus{
        WAITING,
        COMPLETED,
        FAILED
    }
    static class LocatorResult{
        ActualWidgetInfo actualWidgetInfo;
        LocatorStatus status;
        String message;

        LocatorResult(){
            actualWidgetInfo = null;
            status = LocatorStatus.FAILED;
            message = "Initialized";
        }

        LocatorResult(ActualWidgetInfo actualWidgetInfo){
            this();
            if(actualWidgetInfo != null){
                status = LocatorStatus.COMPLETED;
                this.actualWidgetInfo = actualWidgetInfo;
                message = "Completed";
            }
        }
        LocatorResult(LocatorStatus status, String message){
            this();
            this.status = status;
            this.message = message;
        }
        LocatorResult(LocatorStatus status){
            this(status, "S: " + status.name());
        }
    }
    private static long delay = 1000; // TODO: Configurable
    private static final AtomicInteger locatorId = new AtomicInteger(0);

    public final synchronized void locate(LocatableStep locatableStep, Locator.LocatorCallback callback){
        if(callback == null)
            callback = new DummyLocatorCallback();
        locatorId.incrementAndGet();
        Log.d(LatteService.TAG, this.getClass().getSimpleName() +":" + locatorId.intValue() + " locating " + locatableStep);
        Locator.LocatorCallback finalCallback = callback;
        new Handler().post(() -> this.locateTask(locatableStep, finalCallback, locatorId.intValue()));
    }

    @Override
    public synchronized void interrupt() {
        locatorId.incrementAndGet();
    }

    private synchronized void  locateTask(LocatableStep locatableStep, Locator.LocatorCallback callback, int myLocatorId){
        if(locatableStep == null || locatableStep.getTargetWidgetInfo() == null)
        {
            Log.e(LatteService.TAG, this.getClass().getSimpleName()+":" + myLocatorId + " locating null!");
            callback.onError("The locatableStep is null");
            return;
        }
        Log.d(LatteService.TAG, this.getClass().getSimpleName() +":" + myLocatorId + " locating " + locatableStep);
        if(myLocatorId != locatorId.intValue()){
            Log.d(LatteService.TAG, this.getClass().getSimpleName() + " is interrupted!");
            callback.onError("The targetWidget is null");
            return;
        }
        if (locatableStep.reachedMaxLocatingAttempts()){
            Log.d(LatteService.TAG, "Reached max attempt for " + this.getClass().getSimpleName() + " locating " + locatableStep);
            callback.onError("Reached Max Locating Attempt");
            return;
        }
        LocatorResult locatorResult = locateAttempt(locatableStep.getTargetWidgetInfo());
        if (locatorResult == null || locatorResult.status == LocatorStatus.FAILED)
        {
            Log.d(LatteService.TAG, this.getClass().getSimpleName() +":" + myLocatorId + " is FAILED!");
            String errorMessage = locatorResult != null ? locatorResult.message : "No LocatorResult";
            callback.onError(errorMessage);
            return;
        }
        else if (locatorResult.status == LocatorStatus.COMPLETED)
        {
            Log.d(LatteService.TAG, this.getClass().getSimpleName() +":" + myLocatorId+ " is COMPLETED!");
            if (locatorResult.actualWidgetInfo == null)
                callback.onError("Locator is completed but the actualWidgetInfo is null");
            else
                new Handler().post(() -> callback.onCompleted(locatorResult.actualWidgetInfo));
            return;
        }
        else if (locatorResult.status == LocatorStatus.WAITING){
            locatableStep.increaseLocatingAttempts();
            Log.d(LatteService.TAG, this.getClass().getSimpleName() +":" + myLocatorId + " is WAITING! Attempt: " + locatableStep.getNumberOfLocatingAttempts());
            new Handler().postDelayed(() -> this.locateTask(locatableStep, callback, myLocatorId), delay);
            return;
        }
        callback.onError("Unknown Error");
    }

    protected abstract LocatorResult locateAttempt(ConceivedWidgetInfo targetWidget);

    protected ActualWidgetInfo findActualWidget(ConceivedWidgetInfo targetWidget){
        if (targetWidget == null)
            return null;
        List<AccessibilityNodeInfo> similarNodes = Utils.findSimilarNodes(targetWidget);
        if(similarNodes.size() != 1){
            if(similarNodes.size() == 0) {
                Log.e(LatteService.TAG, "The target widget could not be found in current screen.");
                // TODO: For debugging
                Log.d(LatteService.TAG, "The target XPATH: \n\t" + targetWidget.getXpath());
                List<AccessibilityNodeInfo> allNodes = Utils.getAllA11yNodeInfo(false);
                for(AccessibilityNodeInfo nodeInfo : allNodes){
                    ActualWidgetInfo actualWidgetInfo = ActualWidgetInfo.createFromA11yNode(nodeInfo);
                    if (actualWidgetInfo != null)
                        Log.d(LatteService.TAG, "\t" + actualWidgetInfo.getXpath());
                }
            }
            else{
                Log.d(LatteService.TAG, "There are more than one candidates for the target.");
                for(AccessibilityNodeInfo node : similarNodes){
                    Log.d(LatteService.TAG, " Node: " + node);
                }
            }
            return null;
        }
        AccessibilityNodeInfo node = similarNodes.get(0);
        return ActualWidgetInfo.createFromA11yNode(node);
    }
}
