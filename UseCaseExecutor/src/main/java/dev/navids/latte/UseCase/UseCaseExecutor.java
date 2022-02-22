package dev.navids.latte.UseCase;


import android.os.Handler;
import android.util.Log;

import org.json.simple.JSONArray;
import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import dev.navids.latte.Config;
import dev.navids.latte.LatteService;

public class UseCaseExecutor{

    enum ExecutorState{
        IDLE,
        RUNNING,
        NEXT,
        CUSTOM_STEP
    }
    private UseCaseExecutor(){
        stepExecutor = LatteService.getInstance().getStepExecutor("regular");
    }
    private static UseCaseExecutor instance = null;
    public static UseCaseExecutor v(){
        if(instance == null){
            instance = new UseCaseExecutor();
        }
        return instance;
    }

    private UseCase currentUseCase = null;
    private  StepCommand customStep = null;
    public void setStepExecutor(StepExecutor stepExecutor) {
        this.stepExecutor = stepExecutor;
        Log.i(LatteService.TAG, "StepExecutor is set to " + this.stepExecutor);
    }

    private StepExecutor stepExecutor = null;

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
                    if(customStep == null){
                        mode = ExecutorState.IDLE;
                    }
                    else{
                        if(customStep.isDone()){
                            Log.i(LatteService.TAG, "The custom step is done!");
                            writeCustomStepResult();
                            customStep = null;
                            mode = ExecutorState.IDLE;
                        }
                        else {
                            if (customStep.isNotStarted())
                                customStep.setState(StepState.RUNNING);
                            stepExecutor.executeStep(customStep);
                        }
                    }
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
                                currentStep.setState(StepState.RUNNING);
                            if (currentStep instanceof SleepStep) {
                                SleepStep sleepStep = (SleepStep) currentStep;
                                sleepLock = true;
                                Log.i(LatteService.TAG, "Sleep Command " + sleepStep.getSleepTime());
                                new Handler().postDelayed(() -> {
                                    sleepLock = false;
                                    sleepStep.setState(StepState.COMPLETED);
                                }, sleepStep.getSleepTime() * 1000);
                            }
                            else {
                                // The rest of the steps are handled by stepExecutor
                                stepExecutor.executeStep(currentStep);
                            }
                        }
                    }
                    else {
                        writeUseCaseResult();
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

    public synchronized void clearHistory(){
        stop();
        String dir = LatteService.getInstance().getBaseContext().getFilesDir().getPath();
        new File(dir, Config.v().CUSTOM_STEP_RESULT_FILE_NAME).delete();
        new File(dir, Config.v().USECASE_RESULT_FILE_NAME).delete();
    }

    public synchronized void interruptCustomStepExecution(){
        stop();
        customStep = null;
        if(stepExecutor != null)
            stepExecutor.interrupt();
        writeCustomStepResult();
    }

    public synchronized boolean initiateCustomStep(String stepJSONString){
        clearHistory();
        JSONParser jsonParser = new JSONParser();
        try {
            JSONObject stepJSON = (JSONObject) jsonParser.parse(stepJSONString);
            customStep = createStepFromJson(stepJSON);
            Log.i(LatteService.TAG, "CustomStep is created: " + customStep);
            if(customStep instanceof SleepStep) {
                Log.e(LatteService.TAG, "CustomStep cannot be SleepStep.");
                customStep = null;
                return false;
            }
            mode = ExecutorState.CUSTOM_STEP;
            return true;
        } catch (ParseException e) {
            e.printStackTrace();
            Log.e(LatteService.TAG, "CustomStep cannot be created " + e.getLocalizedMessage());
        }
        writeCustomStepResult();
        return false;
    }

    public synchronized void setDelay(long delay){
        this.delay = delay;
        Log.i(LatteService.TAG, "Delay has been set to " + this.delay);
    }

    public synchronized void init(JSONArray commandsJson){
        clearHistory();
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
            StepCommand stepCommand = createStepFromJson(stepJson);
            if(stepCommand == null){
                Log.e(LatteService.TAG, "Json Unknown Step " + stepJson);
                continue;
            }
            steps.add(stepCommand);
        }
        currentUseCase = new UseCase(steps);
        Log.i(LatteService.TAG, String.format("New UseCase is initalized with %d steps", currentUseCase.getStepCount()));
    }

    public static StepCommand createStepFromJson(JSONObject stepJson){
        try {
            String action = (String) stepJson.getOrDefault("action", "UNKNOWN");
            StepCommand stepCommand = null;
            if (SleepStep.isSleepAction(action))
                stepCommand = new SleepStep(stepJson);
            else if (TypeStep.isTypeStep(action))
                stepCommand = new TypeStep(stepJson);
            else if (ClickStep.isClickStep(action))
                stepCommand = new ClickStep(stepJson);
            else if (FocusStep.isFocusStep(action))
                stepCommand = new FocusStep(stepJson);
            else
                stepCommand = null;
            return stepCommand;
        } catch (Exception e) {
            Log.e(LatteService.TAG, "Error in creating Step from Json: " + e.getMessage());
        }
        return null;
    }

    public void writeCustomStepResult() {
        String dir = LatteService.getInstance().getBaseContext().getFilesDir().getPath();
        File file = new File(dir, Config.v().CUSTOM_STEP_RESULT_FILE_NAME);
        Log.i(LatteService.TAG, "Custom Step Result Path: " + file.getAbsolutePath());
        FileWriter myWriter = null;
        try {
            myWriter = new FileWriter(file);
            if(customStep == null || !customStep.isDone()) {
                myWriter.write(String.format(Locale.getDefault(),"   Custom Step $ State: %s $ #Events: %d $ Time: %d $ ActingWidget: %s\n",
                        StepState.FAILED.name(),
                        -1,
                        -1,
                        ""
                ));
                return;
            }
            int number_of_actions = 0;
            String actingWidget = "";
            if (this.customStep instanceof LocatableStep) {
                LocatableStep locatableStep = (LocatableStep) this.customStep;
                number_of_actions = locatableStep.getNumberOfLocatingAttempts() + locatableStep.getNumberOfActingAttempts();
                actingWidget = locatableStep.getActedWidget() != null ? locatableStep.getActedWidget().completeToString(true) : "";
            }
            // TODO: Change the formatting to use JSON
            String message = String.format(Locale.getDefault(),"   Custom Step $ State: %s $ #Events: %d $ Time: %d $ ActingWidget: %s\n",
                    this.customStep.getState().name(),
                    number_of_actions,
                    this.customStep.getTotalTime(),
                    actingWidget
                    );
            myWriter.write(message + "\n");
            myWriter.close();
        } catch (IOException ex) {
            ex.printStackTrace();
            Log.e(LatteService.TAG + "_RESULT", "Error: " + ex.getMessage());
        }
    }

    public void writeUseCaseResult() {
        if(currentUseCase == null || !currentUseCase.isFinished())
            return;
        String fileName = Config.v().USECASE_RESULT_FILE_NAME;
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
