package dev.navids.latte;

import android.os.Build;
import android.util.Log;

import androidx.annotation.RequiresApi;

import org.json.simple.JSONArray;
import org.json.simple.JSONObject;

@RequiresApi(api = Build.VERSION_CODES.N)
public class TypeStep extends LocatableStep {
    public String getText() {
        return text;
    }

    private String text;


    TypeStep(JSONObject stepJson) {
        super(stepJson);
        String text = "";
        if (stepJson.containsKey("action_args")) {
            JSONArray args = (JSONArray) stepJson.get("action_args");
            text = String.valueOf(args.get(0));
        }
        this.text = text;
        Log.i(LatteService.TAG, "Type Step: " + this.getTargetWidgetInfo() + " " + this.text);
    }

    public static boolean isTypeStep(String action){
        return action.equals("send_keys");
    }

    @Override
    public String toString() {
        return String.format("TypeStep{State=%s,WidgetTarget=%s,Text=%s}", getState(), getTargetWidgetInfo(), text);
    }
}
