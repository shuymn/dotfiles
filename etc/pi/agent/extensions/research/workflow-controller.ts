import {
  ASSESS_PHASE_FILE,
  COLLECT_PHASE_FILE,
  type ResearchPhase,
  type ResearchPhaseFile,
} from "./phases";
import type {
  ActiveResearchRun,
  ResearchPhaseOutput,
  ResearchRunSeed,
} from "./types";

export const MAX_COLLECT_LOOPS = 2;

export type QueuedResearchPhase = {
  run: ActiveResearchRun;
  phaseIndex: number;
  phase: ResearchPhase;
};

export type CompleteResearchPhaseInput = {
  latestAssistantText?: string;
  truncateNotes: (text: string) => string;
};

export type ResearchWorkflowDecision =
  | ({ kind: "queued" } & QueuedResearchPhase)
  | { kind: "completed"; runId: string };

type ResearchControl = {
  follow_up_queries?: FollowUpQuery[];
};

type FollowUpQuery = {
  query: string;
  purpose?: string;
  expected_source_type?: string;
  why_it_matters?: string;
};

export class ResearchWorkflowController {
  private activeRun: ActiveResearchRun | undefined;

  start(seed: ResearchRunSeed): QueuedResearchPhase {
    this.activeRun = {
      ...seed,
      nextPhaseIndex: 0,
      phaseOutputs: [],
      phaseInProgress: false,
      collectLoopCount: 0,
    };

    const phase = this.startQueuedPhase();
    if (!phase) throw new Error("Research workflow has no phases to start");
    return phase;
  }

  startQueuedPhase(): QueuedResearchPhase | undefined {
    if (!this.activeRun || this.activeRun.phaseInProgress) return undefined;

    const phaseIndex = this.activeRun.nextPhaseIndex;
    if (phaseIndex >= this.activeRun.phases.length) {
      this.cancel();
      return undefined;
    }

    this.activeRun.nextPhaseIndex += 1;
    this.activeRun.phaseInProgress = true;

    return {
      run: this.activeRun,
      phaseIndex,
      phase: this.activeRun.phases[phaseIndex],
    };
  }

  completePhase(
    input: CompleteResearchPhaseInput,
  ): ResearchWorkflowDecision | undefined {
    if (!this.activeRun?.phaseInProgress) return undefined;

    const run = this.activeRun;
    const completedPhaseIndex = run.nextPhaseIndex - 1;
    const completedPhase = run.phases[completedPhaseIndex];

    if (completedPhase) {
      const output: ResearchPhaseOutput = {
        phaseIndex: completedPhaseIndex,
        phaseFile: completedPhase.file,
        notes: input.truncateNotes(input.latestAssistantText ?? ""),
      };
      run.phaseOutputs.push(output);
    }

    run.phaseInProgress = false;
    const nextPhaseIndex = decideNextPhaseIndex(
      run,
      completedPhaseIndex,
      input.latestAssistantText,
    );

    if (nextPhaseIndex === undefined) {
      const runId = run.id;
      this.activeRun = undefined;
      return { kind: "completed", runId };
    }

    run.nextPhaseIndex = nextPhaseIndex;
    return {
      kind: "queued",
      run,
      phaseIndex: nextPhaseIndex,
      phase: run.phases[nextPhaseIndex],
    };
  }

  cancel(): void {
    this.activeRun = undefined;
  }

  getActiveRun(): ActiveResearchRun | undefined {
    return this.activeRun;
  }

  currentPhaseFile(): ResearchPhaseFile | undefined {
    if (!this.activeRun?.phaseInProgress) return undefined;
    const index = this.activeRun.nextPhaseIndex - 1;
    return index >= 0 ? this.activeRun.phases[index]?.file : undefined;
  }
}

function parseResearchControl(
  text: string | undefined,
): ResearchControl | undefined {
  if (!text) return undefined;

  const matches = [
    ...text.matchAll(/<research_control>\s*([\s\S]*?)\s*<\/research_control>/g),
  ];
  const finalMatch = matches.at(-1);
  if (!finalMatch?.[1]) return undefined;

  try {
    const parsed = JSON.parse(finalMatch[1]) as Record<string, unknown>;
    if (!parsed || typeof parsed !== "object") return undefined;
    return {
      follow_up_queries: normalizeFollowUpQueries(parsed.follow_up_queries),
    };
  } catch {
    return undefined;
  }
}

function normalizeFollowUpQueries(value: unknown): FollowUpQuery[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isFollowUpQuery);
}

function isFollowUpQuery(value: unknown): value is FollowUpQuery {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return typeof record.query === "string" && record.query.trim().length > 0;
}

function findPhaseIndex(
  run: ActiveResearchRun,
  phaseFile: ResearchPhaseFile,
): number {
  const index = run.phases.findIndex((phase) => phase.file === phaseFile);
  if (index < 0)
    throw new Error(`Research workflow phase not found in run: ${phaseFile}`);
  return index;
}

function decideNextPhaseIndex(
  run: ActiveResearchRun,
  completedPhaseIndex: number,
  latestAssistantText: string | undefined,
): number | undefined {
  const completedPhaseFile = run.phases[completedPhaseIndex]?.file;

  if (completedPhaseFile === ASSESS_PHASE_FILE) {
    const control = parseResearchControl(latestAssistantText);
    const hasFollowUpQueries = (control?.follow_up_queries ?? []).length > 0;

    if (hasFollowUpQueries && run.collectLoopCount < MAX_COLLECT_LOOPS) {
      run.collectLoopCount += 1;
      return findPhaseIndex(run, COLLECT_PHASE_FILE);
    }
  }

  const next = completedPhaseIndex + 1;
  return next < run.phases.length ? next : undefined;
}
