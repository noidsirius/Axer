package dev.navids.latte;


import android.os.Build;
import android.view.accessibility.AccessibilityNodeInfo;

import androidx.annotation.RequiresApi;

import org.json.simple.JSONArray;
import org.json.simple.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentLinkedQueue;

@RequiresApi(api = Build.VERSION_CODES.N)
public abstract class WidgetInfo {
    List<String> attributeNames = Arrays.asList(
            "resourceId", "contentDescription", "text", "class", "xpath");
    Map<String, String> attributes = new HashMap<>();

    public WidgetInfo(String resourceId) {
        this(resourceId, "", "", null);
    }
    public WidgetInfo(String resourceId, String contentDescription, String text, String clsName) {
        attributes.put(attributeNames.get(0), resourceId);
        attributes.put(attributeNames.get(1), contentDescription);
        attributes.put(attributeNames.get(2), text);
        attributes.put(attributeNames.get(3), clsName);
    }


    protected String getAttr(String attributeName){
        return attributes.getOrDefault(attributeName, "");
    }

    protected boolean hasAttr(String attributeName){
        String s = attributes.getOrDefault(attributeName, "");
        return s != null && !s.equals("") && !s.equals("null");
    }


    public boolean hasSimilarAttribute(WidgetInfo other, String attributeName)
    {
        return getAttr(attributeName).equals(other.getAttr(attributeName));
    }

    public boolean isSimilar(WidgetInfo other)
    {
        return isSimilar(other, Collections.emptyList());
    }

    public boolean isSimilar(WidgetInfo other, List<String> myMaskedAttributes)
    {
        boolean isSimilar = true;
        for(String attrName : attributeNames){
            if(myMaskedAttributes.contains(attrName))
                continue;
            boolean isSimilarAttribute = hasSimilarAttribute(other, attrName);
            if(!attrName.equals("xpath"))
                isSimilar &= isSimilarAttribute;
        }
        return isSimilar;
    }

    public void setXpath(String xpath) {
        this.attributes.put("xpath", xpath);
    }
    public abstract String getXpath();
}
