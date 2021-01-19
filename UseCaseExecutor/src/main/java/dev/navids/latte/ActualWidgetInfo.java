package dev.navids.latte;

import android.os.Build;
import android.view.accessibility.AccessibilityNodeInfo;

import androidx.annotation.RequiresApi;

import java.util.ArrayList;
import java.util.List;

@RequiresApi(api = Build.VERSION_CODES.N)
public class ActualWidgetInfo extends WidgetInfo {
    AccessibilityNodeInfo node;
    public ActualWidgetInfo(String resourceId, String contentDescription, String text, String clsName, AccessibilityNodeInfo node) {
        super(resourceId, contentDescription, text, clsName);
        this.node = node;

    }

    public static ActualWidgetInfo createFromA11yNode(AccessibilityNodeInfo node){
        if (node == null){
            return null;
        }
        String resourceId = String.valueOf(node.getViewIdResourceName());
        String contentDescription = String.valueOf(node.getContentDescription());
        String text = String.valueOf(node.getText());
        String clsName = String.valueOf(node.getClassName());
        if (clsName.endsWith("Layout")){
            if (text.equals("null") && contentDescription.equals("null")) {
                String tmp = Utils.getFirstText(node);
                if (tmp != null)
                    text = tmp;
                else {
                    tmp = Utils.getFirstContentDescription(node);
                    if (tmp != null)
                        contentDescription = tmp;
                }
            }
        }
        ActualWidgetInfo widgetInfo = new ActualWidgetInfo(resourceId, contentDescription, text, clsName, node);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            widgetInfo.setXpath(widgetInfo.getXpath());
        }
        return widgetInfo;
    }

    @RequiresApi(api = Build.VERSION_CODES.O)
    @Override
    public String getXpath() {
        if(this.hasAttr("xpath"))
            return this.getAttr("xpath");
        List<String> names = new ArrayList<>();
        AccessibilityNodeInfo it = node;
        names.add(0, String.valueOf(it.getClassName()));
        while(it.getParent() != null){

            int count = 0;
            int length = 0;
            String itClsName = String.valueOf(it.getClassName());
            for(int i=0; i<it.getParent().getChildCount(); i++) {
                // TODO: possibility of ArrayIndexOutOfBoundsException

                AccessibilityNodeInfo child = it.getParent().getChild(i);
                if (child == null)
                    continue;
                String childClsName = String.valueOf(child.getClassName());
                if (!child.isVisibleToUser())
                    continue;
                if (itClsName.equals(childClsName))
                    length++;
                if (child.equals(it)) {
                    count = length;
                }
            }
            if(length > 1)
                names.set(0, String.format("%s[%d]", names.get(0), count));
            it = it.getParent();
            names.add(0, String.valueOf(it.getClassName()));
            //            xpath = String.valueOf(it.getClassName()) + "/" + xpath;
        }
        String xpath = "/"+String.join("/", names);
        return xpath;
    }

    @Override
    public boolean hasSimilarAttribute(WidgetInfo other, String attributeName) {
        if(other instanceof ConceivedWidgetInfo)
            return other.hasSimilarAttribute(this, attributeName);
        return super.hasSimilarAttribute(other, attributeName);
    }

    @Override
    public boolean isSimilar(WidgetInfo other) {
        if(other instanceof ConceivedWidgetInfo)
            return other.isSimilar(this);
        return super.isSimilar(other);
    }

    @Override
    public boolean isSimilar(WidgetInfo other, List<String> myMaskedAttributes) {
        if(other instanceof ConceivedWidgetInfo)
            return other.isSimilar(this, myMaskedAttributes);
        return super.isSimilar(other, myMaskedAttributes);
    }

    @Override
    public String toString() {
        return "ActualWidgetInfo{"
                + super.toString()
                + "}";
    }
}
