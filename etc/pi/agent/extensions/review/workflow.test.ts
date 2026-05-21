import { describe, expect, test } from "bun:test";
import { phaseFilesForMode, type WorkflowPhase } from "./phases";
import { type ReviewRunSeed, ReviewWorkflowController } from "./workflow";

function phases(noFix = false): WorkflowPhase[] {
  return phaseFilesForMode(noFix).map((file) => ({
    file,
    instructions: `${file} instructions`,
  }));
}

function seed(noFix = false): ReviewRunSeed {
  return {
    id: "run-1",
    cwd: "/repo",
    targets: [{ path: "src/app.ts", status: "explicit", source: "explicit" }],
    diff: "",
    phases: phases(noFix),
    noFix,
    instructions: "",
  };
}

function complete(
  workflow: ReviewWorkflowController,
  latestAssistantText = "notes",
) {
  return workflow.completePhase({
    latestAssistantText,
    truncateNotes: (text) => text,
  });
}

function advanceRunningPhase(
  workflow: ReviewWorkflowController,
  notes: string,
) {
  const decision = complete(workflow, notes);
  if (decision?.kind === "queued") workflow.startQueuedPhase();
  return decision;
}

function advanceToGapfill(workflow: ReviewWorkflowController): void {
  while (workflow.currentPhaseFile() !== "04-gapfill.md") {
    advanceRunningPhase(workflow, "advance");
  }
}

describe("ReviewWorkflowController", () => {
  test("start marks phase 1 as running", () => {
    const workflow = new ReviewWorkflowController();

    const queued = workflow.start(seed());

    expect(queued.phaseIndex).toBe(0);
    expect(queued.phase.file).toBe("01-recon.md");
    expect(workflow.getActiveRun()).toMatchObject({
      nextPhaseIndex: 1,
      phaseInProgress: true,
    });
  });

  test("does not start another phase while one is already running", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());

    expect(workflow.startQueuedPhase()).toBeUndefined();
    expect(workflow.currentPhaseFile()).toBe("01-recon.md");
    expect(workflow.getActiveRun()).toMatchObject({
      nextPhaseIndex: 1,
      phaseInProgress: true,
    });
  });

  test("agent_end equivalent advances to the next phase", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());

    const decision = complete(workflow, "recon notes");

    expect(decision).toMatchObject({
      kind: "queued",
      phaseIndex: 1,
      phase: { file: "02-hunt.md" },
    });
    expect(workflow.getActiveRun()?.phaseOutputs).toEqual([
      { phaseIndex: 0, phaseFile: "01-recon.md", notes: "recon notes" },
    ]);
    expect(workflow.getActiveRun()?.phaseInProgress).toBe(false);
  });

  test("gapfill control with new_hunt_tasks loops back to Hunt", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());
    advanceToGapfill(workflow);

    const decision = complete(
      workflow,
      '<review_control>{"new_hunt_tasks":[{"question":"q"}]}</review_control>',
    );

    expect(decision).toMatchObject({
      kind: "queued",
      phaseIndex: 1,
      phase: { file: "02-hunt.md" },
    });
    expect(workflow.getActiveRun()?.gapfillLoopCount).toBe(1);
  });

  test("gapfill loop is capped", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());

    for (const expected of ["02-hunt.md", "02-hunt.md", "05-dedupe.md"]) {
      advanceToGapfill(workflow);
      const decision = complete(
        workflow,
        '<review_control>{"new_hunt_tasks":[{"question":"q"}]}</review_control>',
      );
      expect(decision).toMatchObject({ phase: { file: expected } });
      if (decision?.kind === "queued" && expected !== "05-dedupe.md") {
        workflow.startQueuedPhase();
      }
    }
  });

  test("noFix mode excludes Fix and Verify phases", () => {
    const workflow = new ReviewWorkflowController();

    workflow.start(seed(true));

    expect(workflow.getActiveRun()?.phases.map((phase) => phase.file)).toEqual([
      "01-recon.md",
      "02-hunt.md",
      "03-validate.md",
      "04-gapfill.md",
      "05-dedupe.md",
      "06-trace.md",
      "09-summary.md",
    ]);
  });

  test("final phase completion completes and clears active run", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed(true));

    for (let index = 0; index < 6; index += 1) {
      advanceRunningPhase(workflow, `phase ${index}`);
    }
    const decision = complete(workflow, "summary");

    expect(decision).toEqual({ kind: "completed", runId: "run-1" });
    expect(workflow.getActiveRun()).toBeUndefined();
  });

  test("active phase read-only detection respects phase metadata and noFix mode", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());
    expect(workflow.isReadOnlyPhase()).toBe(true);

    for (let index = 0; index < 6; index += 1) {
      complete(workflow, `phase ${index}`);
      workflow.startQueuedPhase();
    }
    expect(workflow.getActiveRun()?.phases[6].file).toBe("07-fix.md");
    expect(workflow.isReadOnlyPhase()).toBe(false);

    for (let index = 6; index < 8; index += 1) {
      complete(workflow, `phase ${index}`);
      workflow.startQueuedPhase();
    }
    expect(workflow.currentPhaseFile()).toBe("09-summary.md");
    expect(workflow.isReadOnlyPhase()).toBe(true);

    const noFixWorkflow = new ReviewWorkflowController();
    noFixWorkflow.start(seed(true));
    expect(noFixWorkflow.isReadOnlyPhase()).toBe(true);
  });
});
