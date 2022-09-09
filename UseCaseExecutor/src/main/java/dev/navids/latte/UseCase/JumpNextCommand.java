package dev.navids.latte.UseCase;

import android.util.Log;

import org.json.simple.JSONObject;

import dev.navids.latte.LatteService;

public class JumpNextCommand extends NavigateCommand {

    JumpNextCommand(JSONObject stepJson) {
        super(stepJson);
        Log.i(LatteService.TAG, "Jump Next Step");
    }

    public static boolean isJumpNextAction(String action){
        return action.equals("jump_next");
    }


    @Override
    public String toString() {
        return "JumpNextStep{" +
                "State=" + getState().name() +
                '}';
    }
}
