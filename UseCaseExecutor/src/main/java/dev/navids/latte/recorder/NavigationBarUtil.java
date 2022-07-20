package dev.navids.latte.recorder;

import android.app.Activity;
import android.content.Context;
import android.content.res.Resources;
import android.graphics.Point;
import android.os.Build;
import android.view.Display;
import android.view.KeyCharacterMap;
import android.view.KeyEvent;
import android.view.ViewConfiguration;
import android.view.WindowManager;

/**
 * @author toby
 * @date 12/10/17
 * @time 3:43 AM
 */
public class NavigationBarUtil {
    public NavigationBarUtil(){

    }
    public boolean isNavigationBarShow(WindowManager windowManager, Context context){
        Display display = windowManager.getDefaultDisplay();
        Point size = new Point();
        Point realSize = new Point();
        display.getSize(size);
        display.getRealSize(realSize);
        return realSize.y!=size.y;
    }

    public int getNavigationBarHeight(Context context) {
        WindowManager windowManager = (WindowManager) context.getSystemService(Context.WINDOW_SERVICE);
        if (!isNavigationBarShow(windowManager, context)){
            return 0;
        }
        Resources resources = context.getResources();
        int resourceId = resources.getIdentifier("navigation_bar_height",
                "dimen", "android");
        int height = resources.getDimensionPixelSize(resourceId);
        return height;
    }

    public int getStatusBarHeight(Context context) {
        int result = 0;
        int resourceId = context.getResources().getIdentifier("status_bar_height", "dimen", "android");
        if (resourceId > 0) {
            result = context.getResources().getDimensionPixelSize(resourceId);
        }
        return result;
    }

}