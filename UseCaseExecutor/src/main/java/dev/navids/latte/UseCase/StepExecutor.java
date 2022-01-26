package dev.navids.latte.UseCase;

public interface StepExecutor {
    boolean executeStep(StepCommand step);
    boolean interrupt();
}
