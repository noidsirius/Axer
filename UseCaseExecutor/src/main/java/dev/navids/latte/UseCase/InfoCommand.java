package dev.navids.latte.UseCase;

import org.json.simple.JSONObject;

public class InfoCommand extends Command {


    private String question = "";
    private JSONObject extra = null;

    InfoCommand(JSONObject stepJson) {
        super(stepJson);
        question = (String) stepJson.getOrDefault("question", "");
        extra = (JSONObject) stepJson.getOrDefault("extra", null);
    }
    @Override
    public JSONObject getJSON() {
        JSONObject jsonObject = super.getJSON();
        jsonObject.put("result", jsonResult == null ? null : jsonResult);
        return jsonObject;
    }

    public String getQuestion() {
        return question;
    }

    public JSONObject getExtra() {
        return extra;
    }

    public JSONObject getJsonResult() {
        return jsonResult;
    }

    public static boolean isInfo(String action){
        return action.equals("info");
    }

    public void setJsonResult(JSONObject jsonResult) {
        this.jsonResult = jsonResult;
    }

    private JSONObject jsonResult = null;
}
