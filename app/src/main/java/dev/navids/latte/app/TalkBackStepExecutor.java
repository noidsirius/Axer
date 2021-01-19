package dev.navids.latte.app;

import android.util.Log;

import dev.navids.latte.LatteService;
import dev.navids.latte.StepCommand;
import dev.navids.latte.StepExecutor;

public class TalkBackStepExecutor implements StepExecutor {
    @Override
    public boolean executeStep(StepCommand step) {
        Log.i(MyLatteService.TAG, "Executing Step " + step);
        return false;
    }
}
