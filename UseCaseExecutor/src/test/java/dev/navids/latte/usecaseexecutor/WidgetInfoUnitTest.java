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

import dev.navids.latte.ConceivedWidgetInfo;
import dev.navids.latte.UseCase.BackCommand;
import dev.navids.latte.UseCase.ClickCommand;
import dev.navids.latte.UseCase.Command;
import dev.navids.latte.UseCase.LocatableCommand;
import dev.navids.latte.UseCase.NextCommand;
import dev.navids.latte.UseCase.PreviousCommand;
import dev.navids.latte.UseCase.SelectCommand;
import dev.navids.latte.UseCase.TypeCommand;

public class WidgetInfoUnitTest {
    private String nodeStr = "{\"a11y_actions\": [\"4\", \"8\", \"64\", \"16908342\"], \"action\": \"click\", \"bounds\": [540, 214, 540, 281], \"checkable\": false, \"checked\": false, \"class_name\": \"android.widget.TextView\", \"clickable\": false, \"clickable_span\": false, \"content_desc\": \"my_content\", \"context_clickable\": false, \"covered\": false, \"drawing_order\": 1, \"enabled\": true, \"focusable\": false, \"focused\": false, \"important_for_accessibility\": true, \"index\": 0, \"invalid\": false, \"is_ad\": false, \"located_by\": \"xpath\", \"long_clickable\": false, \"naf\": false, \"pkg_name\": \"au.gov.nsw.newcastle.app.android\", \"resource_id\": \"my_res\", \"skip\": false, \"text\": \"my_text\", \"visible\": false, \"xpath\": \"/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.view.ViewGroup/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.TextView\"}";

    @Test
    public void conceived_widget_info_test() {
        ConceivedWidgetInfo widgetInfo = new ConceivedWidgetInfo("r1", "c1", "t1", "c2", "/a/b/c2", "xpath");
        assertEquals("r1", widgetInfo.getAttr("resource_id"));
        assertEquals("c1", widgetInfo.getAttr("content_desc"));
        assertEquals("t1", widgetInfo.getAttr("text"));
        assertEquals("c2", widgetInfo.getAttr("class_name"));
        assertEquals("/a/b/c2", widgetInfo.getAttr("xpath"));
        assertTrue(widgetInfo.isLocatedBy("xpath"));
        JSONObject widgetJson = widgetInfo.getJSONCommand("", false, "");
        assertEquals("r1", widgetJson.get("resource_id"));
        assertEquals("c1", widgetJson.get("content_desc"));
        assertEquals("t1", widgetJson.get("text"));
        assertEquals("c2", widgetJson.get("class_name"));
        assertEquals("/a/b/c2", widgetJson.get("xpath"));

    }
}
