package dev.navids.latte.UseCase;

import android.util.Log;

import org.json.simple.JSONObject;

import dev.navids.latte.LatteService;

public class PreviousStep extends NavigateStep {

    PreviousStep(JSONObject stepJson) {
        super(stepJson);
        Log.i(LatteService.TAG, "Previous Step");
    }

    public static boolean isPreviousAction(String action){
        return action.equals("previous");
    }


    @Override
    public String toString() {
        return "PreviousStep{" +
                "State=" + getState().name() +
                '}';
    }
}
