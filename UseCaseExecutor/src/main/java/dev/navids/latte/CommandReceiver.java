package dev.navids.latte;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
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
import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;

import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

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
            case "report_a11y_issues":
            {
//                Parameters
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
                Log.i(LatteService.TAG, "Issue Size: " + returnedResult.size() + " " + results.size());
//                for(AccessibilityHierarchyCheckResult res : results){
//                    Log.i(LatteService.TAG, "    " + res.getType().name() + " " + res.getShortMessage(Locale.getDefault()) + " " + res.getElement().getClassName());
//                }
            }
            break;
            case "set_delay":
                long delay = Long.valueOf(extra);
                UseCaseExecutor.v().setDelay(delay);
                break;
            case "set_step_executor":
                StepExecutor stepExecutor = LatteService.getInstance().getStepExecutor(extra);
                if(stepExecutor != null) {
                    if(extra.equals("talkback"))
                        RegularStepExecutor.is_physical = false;
                    UseCaseExecutor.v().setStepExecutor(stepExecutor);
                }
                break;
            case "set_physical_touch":
                RegularStepExecutor.is_physical = extra.equals("true");
                Log.i(LatteService.TAG, String.format("RegularStepExecutor %suse physical touch", RegularStepExecutor.is_physical ? "" : "does NOT "));
                break;
            default:
                break;
        }
    }
}
