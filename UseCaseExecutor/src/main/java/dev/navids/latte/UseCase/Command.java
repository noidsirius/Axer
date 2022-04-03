package dev.navids.latte.UseCase;

import android.util.Log;

import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;

import dev.navids.latte.LatteService;

public abstract class Command {
    private CommandState state = CommandState.NOT_STARTED;
    private long startTime = -1;
    private long endTime = -1;
    private boolean executeByA11yAssistantService = true; // AKA skip

    Command(JSONObject stepJson){
        boolean skip = (boolean) stepJson.getOrDefault("skip", false);
        this.executeByA11yAssistantService = !skip;
    }

    public static Command createStepFromJson(String stepJsonString){
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

    public static Command createStepFromJson(JSONObject stepJson){
        try {
            String action = (String) stepJson.getOrDefault("action", "UNKNOWN");
            Command command = null;
            if (SleepCommand.isSleepAction(action))
                command = new SleepCommand(stepJson);
            else if (TypeCommand.isTypeStep(action))
                command = new TypeCommand(stepJson);
            else if (ClickCommand.isClickStep(action))
                command = new ClickCommand(stepJson);
            else if (FocusCommand.isFocusStep(action))
                command = new FocusCommand(stepJson);
            else if (NextCommand.isNextAction(action))
                command = new NextCommand(stepJson);
            else if (PreviousCommand.isPreviousAction(action))
                command = new PreviousCommand(stepJson);
            else if (InfoCommand.isInfo(action))
                command = new InfoCommand(stepJson);
            else
                command = null;
            return command;
        } catch (Exception e) {
            Log.e(LatteService.TAG, "Error in creating Step from Json: " + e.getMessage());
        }
        return null;
    }

    public CommandState getState() {
        return state;
    }

    public void setState(CommandState state) {
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
        return state.equals(CommandState.COMPLETED) || state.equals(CommandState.FAILED) || state.equals(CommandState.COMPLETED_BY_HELP);
    }

    public boolean isNotStarted(){
        return state.equals(CommandState.NOT_STARTED);
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

    public enum CommandState {
        NOT_STARTED,
        RUNNING,
        COMPLETED,
        FAILED_PERFORM,
        FAILED_LOCATE,
        FAILED,
        COMPLETED_BY_HELP
    }
}
