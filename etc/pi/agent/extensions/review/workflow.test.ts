import { describe, expect, test } from "bun:test";
import type { ReviewPhaseArtifact } from "./artifacts";
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

function artifact(
  overrides: Partial<ReviewPhaseArtifact> = {},
): ReviewPhaseArtifact {
  return {
    runId: "run-1",
    phaseFile: "01-recon.md",
    findings: [
      {
        id: "finding-1",
        file: "src/app.ts",
        issue: "issue",
        evidence: "evidence",
        impact: "impact",
        suggestedFix: "fix",
        confidence: "confirmed",
      },
    ],
    coverageGaps: [],
    nextTasks: [],
    summaryForNextPhase: "artifact summary",
    ...overrides,
  };
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

  test("records completed phases even when assistant output is empty", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());

    const decision = complete(workflow, "");

    expect(decision).toMatchObject({ kind: "queued", phaseIndex: 1 });
    expect(workflow.getActiveRun()?.phaseOutputs).toEqual([
      { phaseIndex: 0, phaseFile: "01-recon.md", notes: "" },
    ]);
  });

  test("valid structured artifact becomes the phase output instead of assistant prose", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());

    expect(workflow.recordPhaseArtifact(artifact())).toEqual({
      ok: true,
      warnings: [],
    });
    const decision = complete(workflow, "assistant prose fallback");

    expect(decision).toMatchObject({ kind: "queued", phaseIndex: 1 });
    expect(workflow.getActiveRun()?.phaseOutputs).toEqual([
      {
        phaseIndex: 0,
        phaseFile: "01-recon.md",
        notes: "artifact summary",
      },
    ]);
    expect(workflow.getActiveRun()?.phaseArtifacts[0]).toMatchObject({
      artifact: { summaryForNextPhase: "artifact summary" },
      fallbackNotes: undefined,
      warnings: [],
    });
  });

  test("missing artifact falls back to assistant text and records warnings", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());

    const decision = complete(workflow, "fallback notes");

    expect(decision).toMatchObject({ kind: "queued", phaseIndex: 1 });
    expect(workflow.getActiveRun()?.phaseArtifacts[0]).toMatchObject({
      artifact: undefined,
      fallbackNotes: "fallback notes",
      warnings: [{ code: "missing_artifact" }, { code: "fallback_used" }],
    });
  });

  test("invalid artifact falls back without aborting the workflow", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());

    workflow.recordPhaseArtifact(
      artifact({ summaryForNextPhase: "", findings: [] }),
    );
    const decision = complete(workflow, "fallback after invalid artifact");

    expect(decision).toMatchObject({ kind: "queued", phaseIndex: 1 });
    expect(workflow.getActiveRun()?.phaseOutputs[0]).toMatchObject({
      notes: "fallback after invalid artifact",
    });
    expect(workflow.getActiveRun()?.phaseArtifacts[0]).toMatchObject({
      artifact: undefined,
      fallbackNotes: "fallback after invalid artifact",
    });
    expect(
      workflow
        .getActiveRun()
        ?.phaseArtifacts[0].warnings.map((warning) => warning.code),
    ).toContain("missing_field");
  });

  test("invalid patch records warnings but preserves the last valid artifact", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());

    workflow.recordPhaseArtifact(artifact());
    workflow.recordPhaseArtifactPatch({
      runId: "run-1",
      phaseFile: "01-recon.md",
      replaceFindingsById: [
        {
          id: "missing-finding",
          file: "src/app.ts",
          issue: "should not apply",
          evidence: "evidence",
          impact: "impact",
          suggestedFix: "fix",
          confidence: "likely",
        },
      ],
      replaceSummaryForNextPhase: "patched summary",
    });
    const decision = complete(workflow, "fallback not used");

    expect(decision).toMatchObject({ kind: "queued", phaseIndex: 1 });
    expect(workflow.getActiveRun()?.phaseOutputs[0]).toMatchObject({
      notes: "patched summary",
    });
    expect(workflow.getActiveRun()?.phaseArtifacts[0]).toMatchObject({
      artifact: {
        summaryForNextPhase: "patched summary",
        findings: [{ id: "finding-1", issue: "issue" }],
      },
      fallbackNotes: undefined,
    });
    expect(
      workflow
        .getActiveRun()
        ?.phaseArtifacts[0].warnings.map((warning) => warning.code),
    ).toContain("invalid_patch");
  });

  test("malformed artifact with patch falls back instead of throwing", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());

    workflow.recordPhaseArtifact(artifact({ findings: {} as never }));
    workflow.recordPhaseArtifactPatch({
      runId: "run-1",
      phaseFile: "01-recon.md",
      replaceSummaryForNextPhase: "patched summary",
    });

    expect(() =>
      complete(workflow, "fallback after malformed artifact"),
    ).not.toThrow();
    expect(workflow.getActiveRun()?.phaseArtifacts[0]).toMatchObject({
      artifact: undefined,
      fallbackNotes: "fallback after malformed artifact",
    });
    expect(
      workflow
        .getActiveRun()
        ?.phaseArtifacts[0].warnings.map((warning) => warning.code),
    ).toEqual(
      expect.arrayContaining([
        "missing_field",
        "invalid_patch",
        "fallback_used",
      ]),
    );
  });

  test("artifact items with missing required fields fall back", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());

    workflow.recordPhaseArtifact(
      artifact({
        findings: [
          {
            id: "finding-1",
            issue: "issue",
            evidence: "evidence",
            impact: "impact",
            suggestedFix: "fix",
            confidence: "unknown",
          } as never,
        ],
      }),
    );
    complete(workflow, "fallback after missing item field");

    expect(workflow.getActiveRun()?.phaseArtifacts[0]).toMatchObject({
      artifact: undefined,
      fallbackNotes: "fallback after missing item field",
    });
    expect(
      workflow
        .getActiveRun()
        ?.phaseArtifacts[0].warnings.map((warning) => warning.message),
    ).toEqual(
      expect.arrayContaining([
        "findings item is missing file.",
        "findings item has invalid confidence.",
      ]),
    );
  });

  test("artifact finding confidence must be a string enum value", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());

    workflow.recordPhaseArtifact(
      artifact({
        findings: [
          {
            id: "finding-1",
            file: "src/app.ts",
            issue: "issue",
            evidence: "evidence",
            impact: "impact",
            suggestedFix: "fix",
            confidence: ["confirmed"],
          } as never,
        ],
      }),
    );
    complete(workflow, "fallback after non-string confidence");

    expect(workflow.getActiveRun()?.phaseArtifacts[0]).toMatchObject({
      artifact: undefined,
      fallbackNotes: "fallback after non-string confidence",
    });
    expect(
      workflow
        .getActiveRun()
        ?.phaseArtifacts[0].warnings.map((warning) => warning.message),
    ).toContain("findings item has invalid confidence.");
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

  test("gapfill artifact with empty nextTasks overrides legacy control", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());
    advanceToGapfill(workflow);

    workflow.recordPhaseArtifact(
      artifact({ phaseFile: "04-gapfill.md", nextTasks: [] }),
    );
    const decision = complete(
      workflow,
      '<review_control>{"new_hunt_tasks":[{"question":"q"}]}</review_control>',
    );

    expect(decision).toMatchObject({
      kind: "queued",
      phaseIndex: 4,
      phase: { file: "05-dedupe.md" },
    });
    expect(workflow.getActiveRun()?.gapfillLoopCount).toBe(0);
  });

  test("gapfill artifact with nextTasks loops back to Hunt", () => {
    const workflow = new ReviewWorkflowController();
    workflow.start(seed());
    advanceToGapfill(workflow);

    workflow.recordPhaseArtifact(
      artifact({
        phaseFile: "04-gapfill.md",
        nextTasks: [
          {
            id: "task-1",
            question: "q",
            scopeHint: "src/app.ts",
            evidenceToCheck: ["caller"],
            whyItMatters: "could affect decision",
          },
        ],
      }),
    );
    const decision = complete(workflow, "no legacy control");

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
