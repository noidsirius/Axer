package dev.navids.latte;


import android.os.Build;
import android.os.Handler;
import android.util.Log;

import androidx.annotation.RequiresApi;

import org.json.simple.JSONArray;
import org.json.simple.JSONObject;

import java.util.ArrayList;
import java.util.List;

@RequiresApi(api = Build.VERSION_CODES.N)
public class UseCaseExecutor{

    enum ExecutorState{
        IDLE,
        RUNNING,
        NEXT,
        CUSTOM_STEP
    }
    private UseCaseExecutor(){}
    private static UseCaseExecutor instance = null;
    public static UseCaseExecutor v(){
        if(instance == null){
            instance = new UseCaseExecutor();
        }
        return instance;
    }

    private UseCase currentUseCase = null;

    public void setStepExecutor(StepExecutor stepExecutor) {
        this.stepExecutor = stepExecutor;
        Log.i(LatteService.TAG, "StepExecutor is set to " + this.stepExecutor);
    }

    private StepExecutor stepExecutor = new RegularStepExecutor();

    private boolean sleepLock = false;
    private ExecutorState mode = ExecutorState.IDLE;
    private long delay = 2000;
    private long startTime = -1;
    private long totalTime = 0;
    public void run() {
        Log.i(LatteService.TAG, String.format(" --- UseCaseExecutor.run Mode: %s ---", mode.name()));
        try {
            switch (mode) {
                case IDLE:
                    break;
                case CUSTOM_STEP:
                    break;
                case RUNNING:
                    Log.i(LatteService.TAG, "Current UseCase" + currentUseCase);
                    if (currentUseCase != null && !currentUseCase.isFinished()){
                        if(sleepLock) {
                            Log.i(LatteService.TAG, "I'm sleeping!");
                        }
                        StepCommand currentStep = currentUseCase.getCurrentStepCommand();
                        Log.i(LatteService.TAG, "Current Step: " + currentStep);
                        if(currentStep != null && !currentStep.isFinished()) {
                            if (currentStep.isNotStarted())
                                currentStep.setState(StepCommand.StepState.RUNNING);
                            if (currentStep instanceof SleepStep) {
                                SleepStep sleepStep = (SleepStep) currentStep;
                                sleepLock = true;
                                Log.i(LatteService.TAG, "Sleep Command " + sleepStep.getSleepTime());
                                new Handler().postDelayed(() -> {
                                    sleepLock = false;
                                    sleepStep.setState(StepCommand.StepState.COMPLETED);
                                }, sleepStep.getSleepTime() * 1000);
                            }
                            else {
                                stepExecutor.executeStep(currentStep);
                            }
                        }
                    }
                    else {
                        if(startTime != -1) {
                            totalTime += System.currentTimeMillis() - startTime;
                            startTime = -1;
                            Log.i(LatteService.TAG, String.format(" --- TotalTime: %d ---", totalTime));
                        }
                        mode = ExecutorState.IDLE;
                    }
                    break;
            }
        }
        catch (Exception exception){

        }
        new Handler().postDelayed(this::run, delay);
    }

    public boolean start(){
        if(currentUseCase == null || currentUseCase.isFinished())
            return false;
        startTime = System.currentTimeMillis();
        mode = ExecutorState.RUNNING;
        currentUseCase.start();
        Log.i(LatteService.TAG, "UseCaseExecutor is started!");
        return true;
    }

    public void stop(){
        mode = ExecutorState.IDLE;
        if(startTime != -1) {
            totalTime += System.currentTimeMillis() - startTime;
            startTime = -1;
        }
        Log.i(LatteService.TAG, "UseCaseExecutor is stopped!");
    }

    public void setDelay(long delay){
        this.delay = delay;
        Log.i(LatteService.TAG, "Delay has been set to " + this.delay);
    }


    public void init(JSONArray commandsJson){
        sleepLock = false;
        startTime = -1;
        totalTime = 0;
        mode = ExecutorState.IDLE;
        List<StepCommand> steps = new ArrayList<>();
        for(int i=0; i<commandsJson.size(); i++){
            JSONObject stepJson = (JSONObject) commandsJson.get(i);
            if(stepJson == null){
                Log.i(LatteService.TAG, "Json Command is null!");
                continue;
            }
            String action = (String) stepJson.getOrDefault("action", "UNKNOWN");
            StepCommand stepCommand = null;
            if(SleepStep.isSleepAction(action))
                stepCommand = new SleepStep(stepJson);
            else if(TypeStep.isTypeStep(action))
                stepCommand = new TypeStep(stepJson);
            else if(ClickStep.isClickStep(action))
                stepCommand = new ClickStep(stepJson);
            else {
                Log.e(LatteService.TAG, "Json Unknown Action" + action + " " + stepJson);
                continue;
            }
            steps.add(stepCommand);
        }
        currentUseCase = new UseCase(steps);
        Log.i(LatteService.TAG, String.format("New UseCase is initalized with %d steps", currentUseCase.getStepCount()));
    }
}
