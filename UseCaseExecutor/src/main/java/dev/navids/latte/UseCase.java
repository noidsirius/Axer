package dev.navids.latte;

import android.os.Build;
import android.util.Log;

import androidx.annotation.RequiresApi;

import java.util.List;

@RequiresApi(api = Build.VERSION_CODES.N)
public class UseCase {
    private List<StepCommand> steps;
    int currentStepIndex = -1;

    boolean isStarted(){
        return currentStepIndex > -1;
    }

    boolean isFinished(){
        getCurrentStepCommand();
        return currentStepIndex >= steps.size();
    }

    boolean start(){
        if(currentStepIndex != -1)
            return false;
        currentStepIndex = 0;
        return true;
    }

    StepCommand getCurrentStepCommand(){
        if (!(currentStepIndex >=0 && currentStepIndex < steps.size()))
            return null;
        while(steps.get(currentStepIndex).isFinished()){
            Log.i(LatteService.TAG, "Step " + (currentStepIndex+1) + " is completed!");
            currentStepIndex++;
            if(currentStepIndex >= steps.size())
                return null;
        }
        return steps.get(currentStepIndex);
    }

    public int getStepCount(){
        return steps.size();
    }


    public UseCase(List<StepCommand> steps) {
        this.steps = steps;
    }

    @Override
    public String toString() {
        return String.format("UseCase{currentStepIndex=%d, TotalSteps=%d}", currentStepIndex, getStepCount());
    }
}
