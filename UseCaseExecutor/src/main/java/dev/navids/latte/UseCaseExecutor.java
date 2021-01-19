package dev.navids.latte;


import android.os.Build;
import android.os.Handler;
import android.util.Log;

import androidx.annotation.RequiresApi;

import org.json.simple.JSONArray;
import org.json.simple.JSONObject;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
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

    public final static String result_file_name = "test_result.txt";
    private boolean sleepLock = false;
    private ExecutorState mode = ExecutorState.IDLE;
    private long delay = 2000;
    private int enable_id = 0;
    private boolean enabled = false;

    public synchronized void enable(){
        if(enabled)
            return;
        enabled = true;
        new Handler().post(() -> run(enable_id));
    }

    public synchronized void disable(){
        enabled = false;
        sleepLock = false;
        enable_id++;
    }

    public synchronized void run(int my_id) {
        if(!enabled || my_id != enable_id){
            Log.i(LatteService.TAG, " --- An old UseCaseExecutor.run (IGNORED) ---");
            return;
        }
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
                        // Handling Sleep Step
                        if(sleepLock) {
                            Log.i(LatteService.TAG, "I'm sleeping!");
                        }
                        StepCommand currentStep = currentUseCase.getCurrentStepCommand();
                        Log.i(LatteService.TAG, "Current Step: " + currentStep);
                        if(currentStep != null && !currentStep.isDone()) {
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
                                // The rest of the steps are handled by stepExecutor
                                stepExecutor.executeStep(currentStep);
                            }
                        }
                    }
                    else {
                        writeResult();
                        mode = ExecutorState.IDLE;
                    }
                    break;
            }
        }
        catch (Exception exception){
            Log.e(LatteService.TAG, String.format(" Exception inside UseCaseExecutor.run: %s", exception.getLocalizedMessage()));
        }
        // Scheduling the next event
        int next_id = enable_id;
        new Handler().postDelayed(() -> this.run(next_id), delay);
    }

    public synchronized boolean start(){
        if(currentUseCase == null || currentUseCase.isFinished())
            return false;
        mode = ExecutorState.RUNNING;
        currentUseCase.start();
        Log.i(LatteService.TAG, "UseCaseExecutor is started!");
        return true;
    }

    public synchronized void stop(){
        mode = ExecutorState.IDLE;
        Log.i(LatteService.TAG, "UseCaseExecutor is stopped!");
    }

    public synchronized void setDelay(long delay){
        this.delay = delay;
        Log.i(LatteService.TAG, "Delay has been set to " + this.delay);
    }


    public synchronized void init(JSONArray commandsJson){
        // Removing previous result file
        String fileName = result_file_name;
        String dir = LatteService.getInstance().getBaseContext().getFilesDir().getPath();
        File file = new File(dir, fileName);
        file.delete();
        // Resetting attributes
        sleepLock = false;
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


    public void writeResult() {
        if(currentUseCase == null || !currentUseCase.isFinished())
            return;
        String fileName = result_file_name;
        String dir = LatteService.getInstance().getBaseContext().getFilesDir().getPath();

        File file = new File(dir, fileName);
        Log.i(LatteService.TAG, "Result Path: " + file.getAbsolutePath());
        FileWriter myWriter = null;
        try {
            myWriter = new FileWriter(file);
            myWriter.write(currentUseCase.getFinalResult() + "\n");
            myWriter.close();
        } catch (IOException ex) {
            ex.printStackTrace();
            Log.e(LatteService.TAG + "_RESULT", "Error: " + ex.getMessage());
        }
    }
}
