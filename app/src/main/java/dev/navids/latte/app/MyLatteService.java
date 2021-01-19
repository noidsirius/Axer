package dev.navids.latte.app;

import dev.navids.latte.LatteService;

public class MyLatteService extends LatteService {
    static String TAG = "LATTE_SERVICE_APP";
    public MyLatteService() {
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        addStepExecutor("talkback", new TalkBackStepExecutor());
    }
}
