package dev.navids.latte;


import android.util.Log;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class Utils {

    // A11yNodeInfoUtils

    public static List<AccessibilityNodeInfo> getAllA11yNodeInfo(boolean log){
        return getAllA11yNodeInfo(LatteService.getInstance().getRootInActiveWindow(), " /", log);
    }

    public static List<AccessibilityNodeInfo> getAllA11yNodeInfo(AccessibilityNodeInfo rootNode, boolean log){
        return getAllA11yNodeInfo(rootNode, " /", log);
    }

    private static List<AccessibilityNodeInfo> getAllA11yNodeInfo(AccessibilityNodeInfo rootNode, String prefix, boolean log){
        if(rootNode == null) {
            Log.i(LatteService.TAG, "The root node is null!");
            return new ArrayList<>();
        }
        List<AccessibilityNodeInfo> result = new ArrayList<>();
        result.add(rootNode);
        if(log)
            Log.i(LatteService.TAG, prefix + "/" + rootNode.getClassName() + " " + rootNode.getViewIdResourceName() + " " + rootNode.getText() + " " + rootNode.getContentDescription());
        for(int i=0; i<rootNode.getChildCount(); i++)
            result.addAll(getAllA11yNodeInfo(rootNode.getChild(i), " " +prefix+rootNode.getClassName()+"/", log));
        return result;
    }

    public static List<AccessibilityNodeInfo> findSimilarNodes(ConceivedWidgetInfo target){
        return findSimilarNodes(target, Collections.emptyList());
    }

    public static List<AccessibilityNodeInfo> findSimilarNodes(ConceivedWidgetInfo target, List<String> myMaskedAttributes){
        List<AccessibilityNodeInfo> result = new ArrayList<>();
        List<AccessibilityNodeInfo> nonVisibleResult = new ArrayList<>();
        for(AccessibilityNodeInfo node : getAllA11yNodeInfo(false)) {
            if(!node.isVisibleToUser())
                continue;
            ActualWidgetInfo currentNodeInfo = ActualWidgetInfo.createFromA11yNode(node); // TODO: Use Cache
            if (target.isSimilar(currentNodeInfo, myMaskedAttributes)) {
                if(node.isVisibleToUser())
                    result.add(node);
                else
                    nonVisibleResult.add(node);
            }
        }
        if(result.size() == 0)
            result.addAll(nonVisibleResult);
        return result;
    }

    static String getFirstText(AccessibilityNodeInfo node){
        if(node == null)
            return null;
        String text = String.valueOf(node.getText());
        if(!text.equals("null"))
            return text;
        for(int i=0; i<node.getChildCount(); i++){
            text = getFirstText(node.getChild(i));
            if(text != null)
                return text;
        }
        return text;
    }

    static String getFirstContentDescription(AccessibilityNodeInfo node){
        if(node == null)
            return null;
        String text = String.valueOf(node.getContentDescription());
        if(!text.equals("null"))
            return text;
        for(int i=0; i<node.getChildCount(); i++){
            text = getFirstContentDescription(node.getChild(i));
            if(text != null)
                return text;
        }
        return text;
    }
}
