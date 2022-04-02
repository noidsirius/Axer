package dev.navids.latte.controller;

import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.UseCase.LocatableStep;
import dev.navids.latte.UseCase.NavigateStep;

public interface ActionPerformer {
    public interface ExecutorCallback{
        void onCompleted();
        void onCompleted(ActualWidgetInfo navigatedWidget);
        void onError(String message);
    }
    void execute(LocatableStep locatableStep, ActualWidgetInfo actualWidgetInfo, ExecutorCallback callback);
    void navigate(NavigateStep navigateStep, ExecutorCallback callback);
}

class DummyExecutorCallback implements ActionPerformer.ExecutorCallback{

    @Override
    public void onCompleted() {

    }

    @Override
    public void onCompleted(ActualWidgetInfo navigatedWidget) {

    }

    @Override
    public void onError(String message) {

    }
}
