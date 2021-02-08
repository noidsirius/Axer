package dev.navids.latte;


import androidx.annotation.Nullable;

import java.io.Serializable;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public abstract class WidgetInfo implements Serializable {
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


    @Override
    public int hashCode() {
        int prime = 31;
        int result = 1;
        for(String attrName : attributeNames)
            result = result * prime + attrName.hashCode();
        return result;
    }

    @Override
    public boolean equals(@Nullable Object obj) {
        if(!(obj instanceof  WidgetInfo))
            return false;
        return this.isSimilar((WidgetInfo) obj);
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

    @Override
    public String toString() {
        String xpath = "";
//        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
//            xpath = !getXpath().equals("")? " xpath: " + getXpath() : ""; // TODO: it's too long
        String id = hasAttr("resourceId") ? " ID= "+getAttr("resourceId")+", ": "";
        String cd = hasAttr("contentDescription") ? " CD= "+getAttr("contentDescription")+", ": "";
        String tx = hasAttr("text") ? " TX= "+getAttr("text")+", ": "";
        String cl = hasAttr("class") ? " CL= "+getAttr("class")+", ": "";
        return id + cd + tx + cl + xpath;
    }
}
