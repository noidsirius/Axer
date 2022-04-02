package dev.navids.latte.UseCase;

@Deprecated
public interface StepExecutor {
    boolean executeStep(StepCommand step);
    boolean interrupt();
}
