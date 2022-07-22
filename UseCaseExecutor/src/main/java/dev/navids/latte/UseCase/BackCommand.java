package dev.navids.latte.UseCase;

import android.util.Log;

import org.json.simple.JSONObject;

import dev.navids.latte.LatteService;

public class BackCommand extends NavigateCommand {

    BackCommand(JSONObject stepJson) {
        super(stepJson);
        Log.i(LatteService.TAG, "Back Step");
    }

    public static boolean isBackAction(String action){
        return action.equals("back");
    }


    @Override
    public String toString() {
        return "BackStep{" +
                "State=" + getState().name() +
                '}';
    }
}
