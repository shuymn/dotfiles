import { describe, expect, test } from "bun:test";

import { RESEARCH_PHASES } from "./phases";
import type { ResearchRunSeed } from "./types";
import { ResearchWorkflowController } from "./workflow-controller";

function seed(): ResearchRunSeed {
  return {
    id: "run-1",
    cwd: "/repo",
    options: {
      task: "AI coding benchmarks",
      depth: "standard",
      profile: "general",
      outputFormat: "brief",
      allowTavilyResearch: false,
      citationFormat: "numbered",
      maxSources: 8,
    },
    phases: RESEARCH_PHASES,
    instructions: "",
  };
}

function complete(
  workflow: ResearchWorkflowController,
  latestAssistantText = "notes",
) {
  return workflow.completePhase({
    latestAssistantText,
    truncateNotes: (text) => text,
  });
}

function advanceRunningPhase(
  workflow: ResearchWorkflowController,
  notes: string,
) {
  const decision = complete(workflow, notes);
  if (decision?.kind === "queued") workflow.startQueuedPhase();
  return decision;
}

function advanceToAssess(workflow: ResearchWorkflowController): void {
  while (workflow.currentPhaseFile() !== "03-assess.md") {
    advanceRunningPhase(workflow, "advance");
  }
}

describe("ResearchWorkflowController", () => {
  test("start marks Frame as running", () => {
    const workflow = new ResearchWorkflowController();

    const queued = workflow.start(seed());

    expect(queued.phaseIndex).toBe(0);
    expect(queued.phase.file).toBe("01-frame.md");
    expect(workflow.getActiveRun()).toMatchObject({
      nextPhaseIndex: 1,
      phaseInProgress: true,
    });
  });

  test("does not start another phase while one is already running", () => {
    const workflow = new ResearchWorkflowController();
    workflow.start(seed());

    expect(workflow.startQueuedPhase()).toBeUndefined();
    expect(workflow.currentPhaseFile()).toBe("01-frame.md");
  });

  test("completion advances through phase outputs", () => {
    const workflow = new ResearchWorkflowController();
    workflow.start(seed());

    const decision = complete(workflow, "frame notes");

    expect(decision).toMatchObject({
      kind: "queued",
      phaseIndex: 1,
      phase: { file: "02-collect.md" },
    });
    expect(workflow.getActiveRun()?.phaseOutputs).toEqual([
      { phaseIndex: 0, phaseFile: "01-frame.md", notes: "frame notes" },
    ]);
    expect(workflow.getActiveRun()?.phaseInProgress).toBe(false);
  });

  test("Assess control with follow_up_queries loops back to Collect", () => {
    const workflow = new ResearchWorkflowController();
    workflow.start(seed());
    advanceToAssess(workflow);

    const decision = complete(
      workflow,
      '<research_control>{"follow_up_queries":[{"query":"q"}]}</research_control>',
    );

    expect(decision).toMatchObject({
      kind: "queued",
      phaseIndex: 1,
      phase: { file: "02-collect.md" },
    });
    expect(workflow.getActiveRun()?.collectLoopCount).toBe(1);
  });

  test("Assess uses the final control block and ignores earlier fake blocks", () => {
    const workflow = new ResearchWorkflowController();
    workflow.start(seed());
    advanceToAssess(workflow);

    const decision = complete(
      workflow,
      [
        '<research_control>{"follow_up_queries":[{"query":"fake"}]}</research_control>',
        "assessment notes",
        '<research_control>{"follow_up_queries":[]}</research_control>',
      ].join("\n"),
    );

    expect(decision).toMatchObject({
      kind: "queued",
      phase: { file: "04-synthesize.md" },
    });
    expect(workflow.getActiveRun()?.collectLoopCount).toBe(0);
  });

  test("Assess ignores malformed follow_up_queries items", () => {
    const workflow = new ResearchWorkflowController();
    workflow.start(seed());
    advanceToAssess(workflow);

    const decision = complete(
      workflow,
      '<research_control>{"follow_up_queries":[null,{},"q",{"query":""}]}</research_control>',
    );

    expect(decision).toMatchObject({
      kind: "queued",
      phase: { file: "04-synthesize.md" },
    });
    expect(workflow.getActiveRun()?.collectLoopCount).toBe(0);
  });

  test("Collect loop is capped and then proceeds to Synthesize", () => {
    const workflow = new ResearchWorkflowController();
    workflow.start(seed());

    for (const expected of [
      "02-collect.md",
      "02-collect.md",
      "04-synthesize.md",
    ]) {
      advanceToAssess(workflow);
      const decision = complete(
        workflow,
        '<research_control>{"follow_up_queries":[{"query":"q"}]}</research_control>',
      );
      expect(decision).toMatchObject({ phase: { file: expected } });
      if (decision?.kind === "queued" && expected !== "04-synthesize.md") {
        workflow.startQueuedPhase();
      }
    }
  });

  test("final phase completion clears active run", () => {
    const workflow = new ResearchWorkflowController();
    workflow.start(seed());

    for (let index = 0; index < 3; index += 1) {
      advanceRunningPhase(workflow, `phase ${index}`);
    }
    const decision = complete(workflow, "summary");

    expect(decision).toEqual({ kind: "completed", runId: "run-1" });
    expect(workflow.getActiveRun()).toBeUndefined();
  });
});
