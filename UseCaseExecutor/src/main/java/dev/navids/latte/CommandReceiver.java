package dev.navids.latte;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import android.util.Xml;
import android.view.accessibility.AccessibilityNodeInfo;

import com.google.android.apps.common.testing.accessibility.framework.AccessibilityCheckPreset;
import com.google.android.apps.common.testing.accessibility.framework.AccessibilityCheckResult;
import com.google.android.apps.common.testing.accessibility.framework.AccessibilityCheckResultUtils;
import com.google.android.apps.common.testing.accessibility.framework.AccessibilityHierarchyCheck;
import com.google.android.apps.common.testing.accessibility.framework.AccessibilityHierarchyCheckResult;
import com.google.android.apps.common.testing.accessibility.framework.Parameters;
import com.google.android.apps.common.testing.accessibility.framework.checks.ImageContrastCheck;
import com.google.android.apps.common.testing.accessibility.framework.checks.TextContrastCheck;
import com.google.android.apps.common.testing.accessibility.framework.checks.TouchTargetSizeCheck;
import com.google.android.apps.common.testing.accessibility.framework.uielement.AccessibilityHierarchyAndroid;

import org.json.simple.JSONArray;
import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;
import org.xmlpull.v1.XmlSerializer;

import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.io.StringWriter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import dev.navids.latte.UseCase.RegularStepExecutor;
import dev.navids.latte.UseCase.SightedTalkBackStepExecutor;
import dev.navids.latte.UseCase.StepExecutor;
import dev.navids.latte.UseCase.UseCaseExecutor;

public class CommandReceiver extends BroadcastReceiver {
    static final String ACTION_COMMAND_INTENT = "dev.navids.latte.COMMAND";
    static final String ACTION_COMMAND_CODE = "command";
    static final String ACTION_COMMAND_EXTRA = "extra";

    interface CommandEvent {
        void doAction(String extra);
    }
    private Map<String, CommandEvent> commandEventMap = new HashMap<>();

    public CommandReceiver() {
        super();
        // ----------- General ----------------
        commandEventMap.put("is_live", (extra) -> Utils.createFile(String.format(Config.v().IS_LIVE_FILE_PATH_PATTERN, extra), "I'm alive " + extra));
        commandEventMap.put("log", (extra) -> Utils.getAllA11yNodeInfo(true));
        commandEventMap.put("invisible_nodes", (extra) -> LatteService.considerInvisibleNodes = (extra.equals("true")));
        commandEventMap.put("report_a11y_issues", (extra) -> {
            Context context2 = LatteService.getInstance().getApplicationContext();
            Set<AccessibilityHierarchyCheck> contrastChecks = new HashSet<>(Arrays.asList(
                    AccessibilityCheckPreset.getHierarchyCheckForClass(TextContrastCheck.class),
                    AccessibilityCheckPreset.getHierarchyCheckForClass(ImageContrastCheck.class)
            ));
            Set<AccessibilityHierarchyCheck> touchTargetChecks = new HashSet<>(Arrays.asList(
                    AccessibilityCheckPreset.getHierarchyCheckForClass(TouchTargetSizeCheck.class)
            ));
            Set<AccessibilityHierarchyCheck> checks =
                    AccessibilityCheckPreset.getAccessibilityHierarchyChecksForPreset(
                            AccessibilityCheckPreset.LATEST);
            if(extra.equals("contrast"))
                checks = contrastChecks;
            else if(extra.equals("touch"))
                checks = touchTargetChecks;
            AccessibilityNodeInfo rootNode = LatteService.getInstance().getRootInActiveWindow();
            AccessibilityHierarchyAndroid hierarchy = AccessibilityHierarchyAndroid.newBuilder(rootNode, context2).build();
            List<AccessibilityHierarchyCheckResult> results = new ArrayList<>();
            for (AccessibilityHierarchyCheck check : checks) {
                Parameters params = new Parameters();
                params.putCustomTouchTargetSize(39);
                results.addAll(check.runCheckOnHierarchy(hierarchy, null, params));
            }
            List<AccessibilityHierarchyCheckResult> returnedResult = AccessibilityCheckResultUtils.getResultsForType(
                    results, AccessibilityCheckResult.AccessibilityCheckResultType.ERROR);
            returnedResult.addAll(AccessibilityCheckResultUtils.getResultsForType(
                    results, AccessibilityCheckResult.AccessibilityCheckResultType.WARNING));
//            Log.i(LatteService.TAG, "Issue Size: " + returnedResult.size() + " " + results.size());
            StringBuilder report_jsonl = new StringBuilder();
            for (AccessibilityHierarchyCheckResult res: returnedResult) {
                ATFWidgetInfo widgetInfo = ATFWidgetInfo.createFromViewHierarchyElement(res);
                if (widgetInfo == null)
                    continue;
                org.json.JSONObject jsonCommand = widgetInfo.getJSONCommand("", false, "");
                String jsonCommandStr = jsonCommand != null ? jsonCommand.toString() : "Error";
                report_jsonl.append(jsonCommandStr).append("\n");
            }
            Utils.createFile(Config.v().ATF_ISSUES_FILE_PATH, report_jsonl.toString());
        });
        commandEventMap.put("capture_layout", (extra) -> {
            try {
                XmlSerializer serializer = Xml.newSerializer();
                StringWriter stringWriter = new StringWriter();
                serializer.setOutput(stringWriter);
                serializer.startDocument("UTF-8", true);
                serializer.startTag("", "hierarchy");
                serializer.attribute("", "rotation", "0"); // TODO:
                Utils.dumpNodeRec(serializer, 0);
                serializer.endTag("", "hierarchy");
                serializer.endDocument();
                Utils.createFile(Config.v().LAYOUT_FILE_PATH, stringWriter.toString());
            } catch (IOException e) {
                e.printStackTrace();
            }
        });
        // ---------------------------- TalkBack Navigation -----------
        commandEventMap.put("nav_next", (extra) -> TalkBackNavigator.v().changeFocus(null, false));
        commandEventMap.put("nav_prev", (extra) -> TalkBackNavigator.v().changeFocus(null, true));
        commandEventMap.put("nav_select", (extra) -> TalkBackNavigator.v().selectFocus(null));
        commandEventMap.put("nav_current_focus", (extra) -> TalkBackNavigator.v().currentFocus());
        commandEventMap.put("tb_a11y_tree", (extra) -> TalkBackNavigator.v().logTalkBackTreeNodeList(null));
        commandEventMap.put("nav_clear_history", (extra) -> TalkBackNavigator.v().clearHistory());
        commandEventMap.put("nav_api_focus", (extra) -> SightedTalkBackStepExecutor.apiFocus = (extra.equals("true")));
        commandEventMap.put("nav_interrupt", (extra) -> TalkBackNavigator.v().interrupt());
        // --------------------------- UseCase Executor ----------------
        commandEventMap.put("enable", (extra) -> UseCaseExecutor.v().enable());
        commandEventMap.put("disable", (extra) -> UseCaseExecutor.v().disable());
        commandEventMap.put("init", (extra) -> {
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
        });
        commandEventMap.put("start", (extra) -> UseCaseExecutor.v().start());
        commandEventMap.put("stop", (extra) -> UseCaseExecutor.v().stop());
        commandEventMap.put("step_clear", (extra) -> UseCaseExecutor.v().clearHistory());
        commandEventMap.put("step_execute", (extra) -> UseCaseExecutor.v().initiateCustomStep(extra));
        commandEventMap.put("step_interrupt", (extra) -> UseCaseExecutor.v().interruptCustomStepExecution());
        commandEventMap.put("set_delay", (extra) -> UseCaseExecutor.v().setDelay(Long.parseLong(extra)));
        commandEventMap.put("set_step_executor", (extra) -> {
            StepExecutor stepExecutor = LatteService.getInstance().getStepExecutor(extra);
            if(stepExecutor != null) {
                if(extra.equals("talkback"))
                    RegularStepExecutor.is_physical = false;
                UseCaseExecutor.v().setStepExecutor(stepExecutor);
            }
        });
        commandEventMap.put("set_physical_touch", (extra) -> {
            RegularStepExecutor.is_physical = extra.equals("true");
            Log.i(LatteService.TAG, String.format("RegularStepExecutor %suse physical touch", RegularStepExecutor.is_physical ? "" : "does NOT "));
        });
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        String command = intent.getStringExtra(ACTION_COMMAND_CODE);
        String extra = intent.getStringExtra(ACTION_COMMAND_EXTRA);
        // De-sanitizing extra value ["\s\,]
        extra = extra.replace("__^__", "\"")
                .replace("__^^__", " ")
                .replace("__^^^__", ",")
                .replace("__^_^__", "'")
                .replace("__^-^__", "+")
                .replace("__^^^^__", "|")
                .replace("__^_^^__", "$")
                .replace("__^-^^__", "*")
                .replace("__^^_^__", "&")
                .replace("__^^-^__", "[")
                .replace("__^^^^^__", "]"); // TODO: Configurable

        if (command == null || extra == null) {
            Log.e(LatteService.TAG, "The command or extra message is null!");
            return;
        }
        Log.i(LatteService.TAG, String.format("The command %s received!", command + (extra.equals("NONE") ? "" : " - " + extra)));
        try {
            if (command.equals("sequence")) {
                try {
                    JSONParser jsonParser = new JSONParser();
                    JSONArray commandsJson = null;
                    Object obj = null;
                    obj = jsonParser.parse(extra);
                    commandsJson = (JSONArray) obj;
                    for (int i = 0; i < commandsJson.size(); i++) {
                        JSONObject commandJson = (JSONObject) commandsJson.get(i);
                        String commandStr = (String) commandJson.getOrDefault("command", "NONE");
                        String extraStr = (String) commandJson.getOrDefault("extra", "NONE");
                        if (commandEventMap.containsKey(commandStr)) {
                            Log.i(LatteService.TAG, String.format("Executing command %s with extraStr %s!", commandStr, extraStr));
                            commandEventMap.get(commandStr).doAction(extraStr);
                        }
                    }

                } catch (ParseException e) {
                    e.printStackTrace();
                }
            } else {
                if (commandEventMap.containsKey(command))
                    commandEventMap.get(command).doAction(extra);
            }
        }
        catch (Exception e){
            Log.e(LatteService.TAG, "Exception happens during command receiver execution", e);
        }
    }
}
