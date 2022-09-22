package dev.navids.latte.controller;

import android.util.Log;
import android.util.Pair;

import dev.navids.latte.ActionUtils;
import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.ConceivedWidgetInfo;
import dev.navids.latte.LatteService;

public class TalkBackTouchLocator extends BaseLocator{
    @Override
    protected LocatorResult locateAttempt(ConceivedWidgetInfo targetWidget) {
        LocatorResult result = super.locateAttempt(targetWidget);
        if(result.status != LocatorStatus.COMPLETED)
            return result;
        ActualWidgetInfo actualWidgetInfo = result.actualWidgetInfo;
        if(!ActionUtils.isFocusedNodeTarget(actualWidgetInfo.getA11yNodeInfo())){
            Pair<Integer, Integer> clickableCoordinate = ActionUtils.getClickableCoordinate(actualWidgetInfo.getA11yNodeInfo(), true);
            Log.i(LatteService.TAG, "TalkBackTouch taps on the coordinates " + clickableCoordinate.first + " " + clickableCoordinate.second + " to locate!");
            ActionUtils.performTap(clickableCoordinate);
            return new LocatorResult(LocatorStatus.WAITING);
        }
        return new LocatorResult(actualWidgetInfo);
    }
}
