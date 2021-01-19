package dev.navids.latte;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

import androidx.annotation.RequiresApi;

import org.json.simple.JSONArray;
import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.IOException;

@RequiresApi(api = Build.VERSION_CODES.N)
public class CommandReceiver extends BroadcastReceiver {
    static final String ACTION_COMMAND_INTENT = "dev.navids.latte.COMMAND";
    static final String ACTION_COMMAND_CODE = "command";
    static final String ACTION_COMMAND_EXTRA = "extra";

    @Override
    public void onReceive(Context context, Intent intent) {
        String command = intent.getStringExtra(ACTION_COMMAND_CODE);
        String extra = intent.getStringExtra(ACTION_COMMAND_EXTRA);
        // De-sanitizing extra value ["\s\,]
        extra = extra.replace("__^__", "\"").replace("__^^__", " ").replace("__^^^__", ",");

        if (command == null || extra == null) {
            Log.e(LatteService.TAG, "The command or extra message is null!");
            return;
        }
        Log.i(LatteService.TAG, String.format("The command %s received!", command + (extra.equals("NONE") ? "" : " - " + extra)));
        switch (command) {
            case "log":
                Utils.getAllA11yNodeInfo(true);
                break;
            case "init":
                String usecase_path = extra;
                File file = new File(usecase_path);
                JSONParser jsonParser = new JSONParser();
                JSONArray commandsJson = null;
                try (FileReader reader = new FileReader(file)) {
                    // TODO: tons of refactor!
                    //Read JSON file
                    Object obj = jsonParser.parse(reader);
                    commandsJson = (JSONArray) obj;
                    UseCaseExecutor.v().init(commandsJson);
                } catch (IOException | ParseException e) {
                    e.printStackTrace();
                }
                break;
            case "enable":
                UseCaseExecutor.v().enable();
                break;
            case "disable":
                UseCaseExecutor.v().disable();
                break;
            case "start":
                UseCaseExecutor.v().start();
                break;
            case "stop":
                UseCaseExecutor.v().stop();
                break;
            case "do_step":
                UseCaseExecutor.v().executeCustomStep(extra);
                break;
            case "set_delay":
                long delay = Long.valueOf(extra);
                UseCaseExecutor.v().setDelay(delay);
                break;
            case "set_step_executor":
                StepExecutor stepExecutor = LatteService.getInstance().getStepExecutor(extra);
                if(stepExecutor != null)
                    UseCaseExecutor.v().setStepExecutor(stepExecutor);
                break;
            default:
                break;
        }
    }
}
