package dev.navids.latte.UseCase;

import org.json.simple.JSONObject;

public abstract class StepCommand {
    private StepState state = StepState.NOT_STARTED;
    private long startTime = -1;
    private long endTime = -1;
    private boolean executeByA11yAssistantService = true; // AKA skip

    StepCommand(JSONObject stepJson){
        boolean skip = (boolean) stepJson.getOrDefault("skip", false);
        this.executeByA11yAssistantService = !skip;
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
}
