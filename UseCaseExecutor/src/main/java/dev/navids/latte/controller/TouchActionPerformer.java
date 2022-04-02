package dev.navids.latte.controller;
import android.util.Pair;
import dev.navids.latte.ActionUtils;
import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.UseCase.ClickStep;

public class TouchActionPerformer extends BaseActionPerformer {
    @Override
    public boolean executeClick(ClickStep clickStep, ActualWidgetInfo actualWidgetInfo) {
        Pair<Integer, Integer> clickableCoordinate = ActionUtils.getClickableCoordinate(actualWidgetInfo.getA11yNodeInfo(), true);
        return ActionUtils.performTap(clickableCoordinate);
    }
}
