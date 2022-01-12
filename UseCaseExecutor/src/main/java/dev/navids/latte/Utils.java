package dev.navids.latte;


import android.content.Context;
import android.graphics.Point;
import android.graphics.Rect;
import android.util.Log;
import android.view.Display;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityNodeInfo;

import org.xmlpull.v1.XmlSerializer;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class Utils {

    // Files

    public static void deleteFile(String fileName){
        String dir = LatteService.getInstance().getBaseContext().getFilesDir().getPath();
        File file = new File(dir, fileName);
        file.delete();
    }

    public static void createFile(String fileName, String message){
        String dir = LatteService.getInstance().getBaseContext().getFilesDir().getPath();

        File file = new File(dir, fileName);
        Log.i(LatteService.TAG, "Output Path: " + file.getAbsolutePath());
        FileWriter myWriter = null;
        try {
            myWriter = new FileWriter(file);
            myWriter.write(message);
            myWriter.close();
        } catch (IOException ex) {
            ex.printStackTrace();
            Log.e(LatteService.TAG + "_RESULT", "Error: " + ex.getMessage());
        }
    }

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

    // ------------------------ Related to capturing layout -------------------------------

    public static void dumpNodeRec(XmlSerializer serializer, int index) throws IOException {
        AccessibilityNodeInfo root = LatteService.getInstance().getRootInActiveWindow();
        WindowManager windowManager =
                (WindowManager) LatteService.getInstance().getApplication().getSystemService(Context.WINDOW_SERVICE);
        final Display display = windowManager.getDefaultDisplay();
        Point outPoint = new Point();
        display.getRealSize(outPoint);
        int mRealSizeHeight, mRealSizeWidth;
        if (outPoint.y > outPoint.x) {
            mRealSizeHeight = outPoint.y;
            mRealSizeWidth = outPoint.x;
        } else {
            mRealSizeHeight = outPoint.x;
            mRealSizeWidth = outPoint.y;
        }
        dumpNodeRec(root, serializer, index, mRealSizeWidth, mRealSizeHeight);

    }

    private  static Rect getVisibleBoundsInScreen(AccessibilityNodeInfo node, int width, int height) {
        if (node == null) {
            return null;
        }
        // targeted node's bounds
        Rect nodeRect = new Rect();
        node.getBoundsInScreen(nodeRect);
        Rect displayRect = new Rect();
        displayRect.top = 0;
        displayRect.left = 0;
        displayRect.right = width;
        displayRect.bottom = height;
        nodeRect.intersect(displayRect);
        return nodeRect;
    }

    private static void dumpNodeRec(AccessibilityNodeInfo node, XmlSerializer serializer, int index,
                                    int width, int height) throws IOException {
        serializer.startTag("", "node");
        serializer.attribute("", "index", Integer.toString(index));
        serializer.attribute("", "text", safeCharSeqToString(node.getText()));
        serializer.attribute("", "resource-id", safeCharSeqToString(node.getViewIdResourceName()));
        serializer.attribute("", "class", safeCharSeqToString(node.getClassName()));
        serializer.attribute("", "package", safeCharSeqToString(node.getPackageName()));
        serializer.attribute("", "content-desc", safeCharSeqToString(node.getContentDescription()));
        serializer.attribute("", "checkable", Boolean.toString(node.isCheckable()));
        serializer.attribute("", "checked", Boolean.toString(node.isChecked()));
        serializer.attribute("", "clickable", Boolean.toString(node.isClickable()));
        serializer.attribute("", "enabled", Boolean.toString(node.isEnabled()));
        serializer.attribute("", "focusable", Boolean.toString(node.isFocusable()));
        serializer.attribute("", "focused", Boolean.toString(node.isFocused()));
        serializer.attribute("", "scrollable", Boolean.toString(node.isScrollable()));
        serializer.attribute("", "long-clickable", Boolean.toString(node.isLongClickable()));
        serializer.attribute("", "password", Boolean.toString(node.isPassword()));
        serializer.attribute("", "selected", Boolean.toString(node.isSelected()));
        serializer.attribute("", "bounds", getVisibleBoundsInScreen(node, width, height).toShortString());
        int count = node.getChildCount();
        for (int i = 0; i < count; i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) {
                if (child.isVisibleToUser()) {
                    dumpNodeRec(child, serializer, i, width, height);
                    child.recycle();
                } else {
                    Log.i(LatteService.TAG, String.format("Skipping invisible child: %s", child.toString()));
                }
            } else {
                Log.i(LatteService.TAG, String.format("Null child %d/%d, parent: %s",
                        i, count, node.toString()));
            }
        }
        serializer.endTag("", "node");
    }

    private static String stripInvalidXMLChars(CharSequence cs) {
        StringBuffer ret = new StringBuffer();
        char ch;
        /* http://www.w3.org/TR/xml11/#charsets
        [#x1-#x8], [#xB-#xC], [#xE-#x1F], [#x7F-#x84], [#x86-#x9F], [#xFDD0-#xFDDF],
        [#x1FFFE-#x1FFFF], [#x2FFFE-#x2FFFF], [#x3FFFE-#x3FFFF],
        [#x4FFFE-#x4FFFF], [#x5FFFE-#x5FFFF], [#x6FFFE-#x6FFFF],
        [#x7FFFE-#x7FFFF], [#x8FFFE-#x8FFFF], [#x9FFFE-#x9FFFF],
        [#xAFFFE-#xAFFFF], [#xBFFFE-#xBFFFF], [#xCFFFE-#xCFFFF],
        [#xDFFFE-#xDFFFF], [#xEFFFE-#xEFFFF], [#xFFFFE-#xFFFFF],
        [#x10FFFE-#x10FFFF].
         */
        for (int i = 0; i < cs.length(); i++) {
            ch = cs.charAt(i);

            if((ch >= 0x1 && ch <= 0x8) || (ch >= 0xB && ch <= 0xC) || (ch >= 0xE && ch <= 0x1F) ||
                    (ch >= 0x7F && ch <= 0x84) || (ch >= 0x86 && ch <= 0x9f) ||
                    (ch >= 0xFDD0 && ch <= 0xFDDF) || (ch >= 0x1FFFE && ch <= 0x1FFFF) ||
                    (ch >= 0x2FFFE && ch <= 0x2FFFF) || (ch >= 0x3FFFE && ch <= 0x3FFFF) ||
                    (ch >= 0x4FFFE && ch <= 0x4FFFF) || (ch >= 0x5FFFE && ch <= 0x5FFFF) ||
                    (ch >= 0x6FFFE && ch <= 0x6FFFF) || (ch >= 0x7FFFE && ch <= 0x7FFFF) ||
                    (ch >= 0x8FFFE && ch <= 0x8FFFF) || (ch >= 0x9FFFE && ch <= 0x9FFFF) ||
                    (ch >= 0xAFFFE && ch <= 0xAFFFF) || (ch >= 0xBFFFE && ch <= 0xBFFFF) ||
                    (ch >= 0xCFFFE && ch <= 0xCFFFF) || (ch >= 0xDFFFE && ch <= 0xDFFFF) ||
                    (ch >= 0xEFFFE && ch <= 0xEFFFF) || (ch >= 0xFFFFE && ch <= 0xFFFFF) ||
                    (ch >= 0x10FFFE && ch <= 0x10FFFF))
                ret.append(".");
            else
                ret.append(ch);
        }
        return ret.toString();
    }

    private static String safeCharSeqToString(CharSequence cs) {
        if (cs == null)
            return "";
        else {
            return stripInvalidXMLChars(cs);
        }
    }

}
