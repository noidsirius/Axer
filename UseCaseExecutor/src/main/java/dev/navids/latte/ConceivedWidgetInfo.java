package dev.navids.latte;

import android.os.Build;

import androidx.annotation.RequiresApi;

import org.json.simple.JSONObject;

import java.util.Collections;
import java.util.List;

@RequiresApi(api = Build.VERSION_CODES.N)
public class ConceivedWidgetInfo extends WidgetInfo {

    String locatedBy = "";

    public ConceivedWidgetInfo(String resourceId, String contentDescription, String text, String clsName, String xpath, String locatedBy) {
        super(resourceId, contentDescription, text, clsName);
        if(!xpath.equals("")) {
            // TODO: handle xpath with content description
            // TODO: handle partial xpath
            if(xpath.startsWith("/hierarchy"))
                xpath = xpath.substring("/hierarchy".length());
            this.setXpath(xpath);
        }
        this.locatedBy = locatedBy;
    }

    public static ConceivedWidgetInfo createFromJson(JSONObject cmd) {
        if(cmd == null)
            return null;
        String resourceId = (String) cmd.getOrDefault("resourceId", "");
        String contentDescription = (String) cmd.getOrDefault("contentDescription", "");
        String text = (String) cmd.getOrDefault("text", "");
        String clsName = (String) cmd.getOrDefault("class", "");
        String xpath = (String) cmd.getOrDefault("xpath", "");
        String locatedBy = (String) cmd.getOrDefault("located_by", "");
        // TODO: Context
        return new ConceivedWidgetInfo(resourceId, contentDescription,text, clsName, xpath, locatedBy);
    }

    public boolean isLocatedBy(String locatedBy) {
        return this.locatedBy.equals(locatedBy);
    }

    @Override
    public boolean hasSimilarAttribute(WidgetInfo other, String attributeName) {
        if(this.isLocatedBy(attributeName))
            if(!this.hasAttr(attributeName) || !other.hasAttr(attributeName))
                return false;
        if(!this.hasAttr(attributeName))
            return !other.hasAttr(attributeName);
        return getAttr(attributeName).equals(other.getAttr(attributeName));
    }

    @Override
    public boolean isSimilar(WidgetInfo other) {
        return isSimilar(other, Collections.emptyList());
    }

    @Override
    public boolean isSimilar(WidgetInfo other, List<String> myMaskedAttributes) {
        boolean isSimilar = true;
        for(String attrName : attributeNames){
            if(myMaskedAttributes.contains(attrName))
                continue;
            boolean isSimilarAttribute = hasSimilarAttribute(other, attrName);
            if(isLocatedBy(attrName)) {
                return isSimilarAttribute;
            }
            if(!attrName.equals("xpath"))
                isSimilar &= isSimilarAttribute;
        }
        return isSimilar;
    }

    @RequiresApi(api = Build.VERSION_CODES.N)
    @Override
    public String getXpath() {
        return getAttr("xpath");
    }
}
