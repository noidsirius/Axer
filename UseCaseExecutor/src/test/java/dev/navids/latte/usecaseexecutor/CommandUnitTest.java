package dev.navids.latte.usecaseexecutor;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;
import org.junit.Assert;
import org.junit.Test;

import java.util.HashMap;
import java.util.Map;

import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.ConceivedWidgetInfo;
import dev.navids.latte.UseCase.BackCommand;
import dev.navids.latte.UseCase.ClickCommand;
import dev.navids.latte.UseCase.Command;
import dev.navids.latte.UseCase.LocatableCommand;
import dev.navids.latte.UseCase.NextCommand;
import dev.navids.latte.UseCase.PreviousCommand;
import dev.navids.latte.UseCase.SelectCommand;
import dev.navids.latte.UseCase.TypeCommand;

public class CommandUnitTest {
    private String targetNodeStr = "{\"a11y_actions\": [\"4\", \"8\", \"64\", \"16908342\"], \"action\": \"click\", \"bounds\": [540, 214, 540, 281], \"checkable\": false, \"checked\": false, \"class_name\": \"android.widget.TextView\", \"clickable\": false, \"clickable_span\": false, \"content_desc\": \"my_content\", \"context_clickable\": false, \"covered\": false, \"drawing_order\": 1, \"enabled\": true, \"focusable\": false, \"focused\": false, \"important_for_accessibility\": true, \"index\": 0, \"invalid\": false, \"is_ad\": false, \"located_by\": \"xpath\", \"long_clickable\": false, \"naf\": false, \"pkg_name\": \"au.gov.nsw.newcastle.app.android\", \"resource_id\": \"my_res\", \"skip\": false, \"text\": \"my_text\", \"visible\": false, \"xpath\": \"/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.view.ViewGroup/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.TextView\"}";
    @Test
    public void command_creation_test() {
        Map<String, Object> commandMap = new HashMap<String, Object>(){
            {put("action", "NOP");}
        };
        JSONObject jsonCommand = new JSONObject(commandMap);
        Command command = Command.createCommandFromJSON(jsonCommand.toJSONString());
        Assert.assertNull(command);
        jsonCommand.put("action", "back");
        Assert.assertTrue(Command.createCommandFromJSON(jsonCommand) instanceof BackCommand);
        jsonCommand.put("action", "next");
        Assert.assertTrue(Command.createCommandFromJSON(jsonCommand) instanceof NextCommand);
        jsonCommand.put("action", "previous");
        Assert.assertTrue(Command.createCommandFromJSON(jsonCommand) instanceof PreviousCommand);
        jsonCommand.put("action", "select");
        Command select_command = Command.createCommandFromJSON(jsonCommand);
        Assert.assertTrue(select_command instanceof SelectCommand);
        Assert.assertTrue(select_command.isNotStarted());
    }

    @Test
    public void locatable_command_test() throws ParseException {
        assertTrue(LocatableCommand.isLocatableAction("click"));
        assertTrue(LocatableCommand.isLocatableAction("type"));
        assertFalse(LocatableCommand.isLocatableAction("back"));
        assertFalse(LocatableCommand.isLocatableAction("next"));
        assertFalse(LocatableCommand.isLocatableAction("select"));
        String commandStr = "{\"action\": \"locate\", \"target\": " + targetNodeStr + "}";
        JSONParser jsonParser = new JSONParser();
        JSONObject stepJSON = (JSONObject) jsonParser.parse(commandStr);
        LocatableCommand customLocatableCommand = new LocatableCommand(stepJSON) {};
        ConceivedWidgetInfo targetWidgetInfo = customLocatableCommand.getTargetWidgetInfo();
        assertEquals("my_text", targetWidgetInfo.getAttr("text"));
        assertEquals("my_res", targetWidgetInfo.getAttr("resource_id"));
        assertEquals("android.widget.TextView", targetWidgetInfo.getAttr("class_name"));
        assertEquals("my_content", targetWidgetInfo.getAttr("content_desc"));
        assertTrue(targetWidgetInfo.getXpath().startsWith("/android.widget.FrameLayout/android.widget.LinearLayout/"));
        assertTrue(targetWidgetInfo.getXpath().endsWith("/android.widget.FrameLayout/android.widget.TextView"));
        assertTrue(targetWidgetInfo.isLocatedBy("xpath"));
    }

    @Test
    public void click_command_test(){
        String clickCommandStr = "{\"action\": \"click\", \"target\": " + targetNodeStr + "}";
        Command command = Command.createCommandFromJSON(clickCommandStr);
        assertTrue(command instanceof ClickCommand);
    }

    @Test
    public void type_command_test(){
        String typeCommandStr = "{\"action\": \"type\", \"text\": \"NewText\", \"target\": " + targetNodeStr + "}";
        Command command = Command.createCommandFromJSON(typeCommandStr);
        assertTrue(command instanceof TypeCommand);
        TypeCommand typeCommand = (TypeCommand) command;
        assertEquals("NewText", typeCommand.getText());
    }
}
