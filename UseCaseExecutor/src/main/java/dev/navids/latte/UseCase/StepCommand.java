package dev.navids.latte.UseCase;

import android.util.Log;

import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;

import dev.navids.latte.LatteService;

public abstract class StepCommand {
    private StepState state = StepState.NOT_STARTED;
    private long startTime = -1;
    private long endTime = -1;
    private boolean executeByA11yAssistantService = true; // AKA skip

    StepCommand(JSONObject stepJson){
        boolean skip = (boolean) stepJson.getOrDefault("skip", false);
        this.executeByA11yAssistantService = !skip;
    }

    public static StepCommand createStepFromJson(String stepJsonString){
        JSONParser jsonParser = new JSONParser();
        try {
            JSONObject stepJSON = (JSONObject) jsonParser.parse(stepJsonString);
            return createStepFromJson(stepJSON);
        } catch (ParseException e) {
            e.printStackTrace();
            Log.e(LatteService.TAG, "CustomStep cannot be created " + e.getLocalizedMessage());
        }
        return null;
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
            else if (NextStep.isNextAction(action))
                stepCommand = new NextStep(stepJson);
            else if (PreviousStep.isPreviousAction(action))
                stepCommand = new PreviousStep(stepJson);
            else
                stepCommand = null;
            return stepCommand;
        } catch (Exception e) {
            Log.e(LatteService.TAG, "Error in creating Step from Json: " + e.getMessage());
        }
        return null;
    }

    public StepState getState() {
        return state;
    }

    public void setState(StepState state) {
        this.state = state;
        switch (state){
            case NOT_STARTED:
                startTime = endTime = -1;
                break;
            case RUNNING:
                if(startTime == -1) {
                    startTime = System.currentTimeMillis();
                    endTime = -1;
                }
                break;
            case COMPLETED:
            case FAILED_PERFORM:
            case FAILED_LOCATE:
            case FAILED:
            case COMPLETED_BY_HELP:
                if(startTime != -1 && endTime == -1)
                    endTime = System.currentTimeMillis();
                break;
        }
    }

    public long getTotalTime(){
        return endTime - startTime;
    }

    public boolean isDone(){
        return state.equals(StepState.COMPLETED) || state.equals(StepState.FAILED) || state.equals(StepState.COMPLETED_BY_HELP);
    }

    public boolean isNotStarted(){
        return state.equals(StepState.NOT_STARTED);
    }

    public boolean shouldExecuteByA11yAssistantService() {
        return executeByA11yAssistantService;
    }

    public JSONObject getJSON(){
        JSONObject jsonObject = new JSONObject();
        jsonObject.put("duration", getTotalTime());
        jsonObject.put("type", this.getClass().getSimpleName());
        jsonObject.put("state", this.getState().name());
        return jsonObject;
    }
}
