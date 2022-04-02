package dev.navids.latte.controller;

import android.util.Log;

import java.io.File;

import dev.navids.latte.ActualWidgetInfo;
import dev.navids.latte.Config;
import dev.navids.latte.LatteService;
import dev.navids.latte.UseCase.LocatableStep;
import dev.navids.latte.UseCase.NavigateStep;
import dev.navids.latte.UseCase.StepCommand;
import dev.navids.latte.UseCase.StepState;
import dev.navids.latte.Utils;

public class Controller {
    private Locator locator;
    private ActionPerformer actionPerformer;
    public Controller(Locator locator, ActionPerformer actionPerformer){
        this.locator = locator;
        this.actionPerformer = actionPerformer;
    }

    public void clearResult(){
        String dir = LatteService.getInstance().getBaseContext().getFilesDir().getPath();
        new File(dir, Config.v().CONTROLLER_RESULT_FILE_NAME).delete();
    }

    public void interrupt(){
        locator.interrupt();
    }

    public void executeCommand(String stepCommandJson){
        StepCommand command = StepCommand.createStepFromJson(stepCommandJson);
        executeCommand(command);
    }

    public void executeCommand(StepCommand command){
        clearResult();
        if(command == null){
            Log.e(LatteService.TAG, "The incoming Command is null!");
            writeResult(null);
            return;
        }

        command.setState(StepState.RUNNING);
        if(command instanceof LocatableStep){
            executeLocatableStep((LocatableStep) command);
        }
        else if (command instanceof NavigateStep){
            navigate(command, (NavigateStep) command);
        }
    }

    private void navigate(StepCommand command, NavigateStep navigateStep) {
        ActionPerformer.ExecutorCallback callback = new ActionPerformer.ExecutorCallback() {
            @Override
            public void onCompleted() {
                onCompleted(null);
            }

            @Override
            public void onCompleted(ActualWidgetInfo navigatedWidget) {
                command.setState(StepState.COMPLETED);
                navigateStep.setNavigatedWidget(navigatedWidget);
                writeResult(navigateStep);
            }

            @Override
            public void onError(String message) {
                navigateStep.setState(StepState.FAILED_PERFORM);
                Log.e(LatteService.TAG, String.format("Error in navigating command %s. Message: %s", navigateStep, message));
                writeResult(navigateStep);
            }
        };
        try {
            actionPerformer.navigate(navigateStep, callback);
        }
        catch (Exception e){
            navigateStep.setState(StepState.FAILED);
            Log.e(LatteService.TAG, String.format("An exception happened navigating command %s. Message: %s", navigateStep, e.getMessage()));
            writeResult(navigateStep);
        }
    }

    private void executeLocatableStep(LocatableStep locatableStep) {
        Locator.LocatorCallback locatorCallback = new Locator.LocatorCallback() {
            @Override
            public void onCompleted(ActualWidgetInfo actualWidgetInfo) {
                locatableStep.setActedWidget(actualWidgetInfo);
                Log.i(LatteService.TAG, String.format("Performing command %s on Widget %s", locatableStep, actualWidgetInfo));
                actionPerformer.execute(locatableStep, actualWidgetInfo, new ActionPerformer.ExecutorCallback() {
                    @Override
                    public void onCompleted() {
                        onCompleted(null);
                    }

                    @Override
                    public void onCompleted(ActualWidgetInfo navigatedWidget) {
                        locatableStep.setState(StepState.COMPLETED);
                        writeResult(locatableStep);
                    }

                    @Override
                    public void onError(String message) {
                        locatableStep.setState(StepState.FAILED_PERFORM);
                        Log.e(LatteService.TAG, String.format("Error in performing command %s. Message: %s", locatableStep, message));
                        writeResult(locatableStep);
                    }
                });
            }

            @Override
            public void onError(String message) {
                locatableStep.setState(StepState.FAILED_LOCATE);
                Log.e(LatteService.TAG, String.format("Error in locating command %s. Message: %s", locatableStep, message));
                writeResult(locatableStep);
            }
        };
        try {
            locator.locate(locatableStep, locatorCallback);
        }
        catch (Exception e){
            locatableStep.setState(StepState.FAILED);
            Log.e(LatteService.TAG, String.format("An exception happened executing command %s. Message: %s", locatableStep, e.getMessage()));
            writeResult(locatableStep);
        }
    }

    private void writeResult(StepCommand stepCommand){
        String jsonCommandStr = stepCommand != null ? stepCommand.getJSON().toString() : "Error";
        Utils.createFile(Config.v().CONTROLLER_RESULT_FILE_NAME, jsonCommandStr);
    }
}
