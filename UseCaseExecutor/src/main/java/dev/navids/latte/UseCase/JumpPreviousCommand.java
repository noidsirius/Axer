package dev.navids.latte.UseCase;

import android.util.Log;

import org.json.simple.JSONObject;

import dev.navids.latte.LatteService;

public class JumpPreviousCommand extends NavigateCommand {

    JumpPreviousCommand(JSONObject stepJson) {
        super(stepJson);
        Log.i(LatteService.TAG, "Jump Previous Step");
    }

    public static boolean isJumpPreviousAction(String action){
        return action.equals("jump_previous");
    }


    @Override
    public String toString() {
        return "JumpPreviousStep{" +
                "State=" + getState().name() +
                '}';
    }
}
