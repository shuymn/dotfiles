import type { Target } from "../lib/git";
import type {
  PendingPhaseArtifactState,
  PhaseArtifactStatus,
  ReviewArtifactWarning,
  ReviewPhaseArtifact,
  ReviewPhaseArtifactPatch,
} from "./artifacts";
import { finalizeReviewPhaseArtifact, hasMaterialNextTasks } from "./artifacts";
import {
  DEDUPE_PHASE_FILE,
  GAPFILL_PHASE_FILE,
  HUNT_PHASE_FILE,
  isReadOnlyPhaseFile,
  type WorkflowPhase,
  type WorkflowPhaseFile,
} from "./phases";

export const MAX_GAPFILL_LOOPS = 2;

export type PhaseOutput = {
  phaseIndex: number;
  phaseFile: string;
  notes: string;
};

export type ReviewRunSeed = {
  id: string;
  cwd: string;
  targets: Target[];
  diff: string;
  phases: WorkflowPhase[];
  noFix: boolean;
  instructions: string;
};

export type ActiveReviewRun = ReviewRunSeed & {
  nextPhaseIndex: number;
  phaseOutputs: PhaseOutput[];
  phaseArtifacts: PhaseArtifactStatus[];
  pendingArtifact?: PendingPhaseArtifactState;
  phaseInProgress: boolean;
  gapfillLoopCount: number;
};

type ReviewControl = {
  new_hunt_tasks?: unknown[];
};

export type QueuedPhase = {
  run: ActiveReviewRun;
  phaseIndex: number;
  phase: WorkflowPhase;
};

export type CompletePhaseInput = {
  latestAssistantText?: string;
  truncateNotes: (text: string) => string;
};

export type WorkflowDecision =
  | ({ kind: "queued" } & QueuedPhase)
  | { kind: "completed"; runId: string };

export type RecordArtifactResult =
  | { ok: true; warnings: ReviewArtifactWarning[] }
  | { ok: false; reason: string; warnings: ReviewArtifactWarning[] };

export class ReviewWorkflowController {
  private activeRun: ActiveReviewRun | undefined;

  start(seed: ReviewRunSeed): QueuedPhase {
    this.activeRun = {
      ...seed,
      nextPhaseIndex: 0,
      phaseOutputs: [],
      phaseArtifacts: [],
      pendingArtifact: undefined,
      phaseInProgress: false,
      gapfillLoopCount: 0,
    };

    const phase = this.startQueuedPhase();
    if (!phase) throw new Error("Review workflow has no phases to start");
    return phase;
  }

  startQueuedPhase(): QueuedPhase | undefined {
    if (!this.activeRun || this.activeRun.phaseInProgress) return undefined;

    const phaseIndex = this.activeRun.nextPhaseIndex;
    if (phaseIndex >= this.activeRun.phases.length) {
      this.cancel();
      return undefined;
    }

    this.activeRun.nextPhaseIndex += 1;
    this.activeRun.phaseInProgress = true;
    this.activeRun.pendingArtifact = emptyPendingArtifact();

    return {
      run: this.activeRun,
      phaseIndex,
      phase: this.activeRun.phases[phaseIndex],
    };
  }

  recordPhaseArtifact(artifact: ReviewPhaseArtifact): RecordArtifactResult {
    const validation = this.validateActivePhaseSubmission(
      artifact.runId,
      artifact.phaseFile,
    );
    if (!validation.ok) return validation;
    validation.run.pendingArtifact ??= emptyPendingArtifact();
    validation.run.pendingArtifact.artifact = artifact;
    validation.run.pendingArtifact.warnings.push(...validation.warnings);
    return { ok: true, warnings: validation.warnings };
  }

  recordPhaseArtifactPatch(
    patch: ReviewPhaseArtifactPatch,
  ): RecordArtifactResult {
    const validation = this.validateActivePhaseSubmission(
      patch.runId,
      patch.phaseFile,
    );
    if (!validation.ok) return validation;
    validation.run.pendingArtifact ??= emptyPendingArtifact();
    validation.run.pendingArtifact.patches.push(patch);
    validation.run.pendingArtifact.warnings.push(...validation.warnings);
    return { ok: true, warnings: validation.warnings };
  }

  completePhase(input: CompletePhaseInput): WorkflowDecision | undefined {
    if (!this.activeRun?.phaseInProgress) return undefined;

    const run = this.activeRun;
    const completedPhaseIndex = run.nextPhaseIndex - 1;
    let completedArtifact: PhaseArtifactStatus | undefined;

    if (completedPhaseIndex >= 0 && completedPhaseIndex < run.phases.length) {
      const phaseFile = run.phases[completedPhaseIndex].file;
      completedArtifact = finalizeReviewPhaseArtifact({
        runId: run.id,
        phaseIndex: completedPhaseIndex,
        phaseFile,
        pending: run.pendingArtifact,
        latestAssistantText: input.latestAssistantText,
        truncateFallback: input.truncateNotes,
      });
      run.phaseArtifacts.push(completedArtifact);
      run.phaseOutputs.push({
        phaseIndex: completedPhaseIndex,
        phaseFile,
        notes: completedArtifact.artifact
          ? completedArtifact.artifact.summaryForNextPhase
          : (completedArtifact.fallbackNotes ?? ""),
      });
    }

    run.pendingArtifact = undefined;
    run.phaseInProgress = false;
    const nextPhaseIndex = decideNextPhaseIndex(
      run,
      completedPhaseIndex,
      input.latestAssistantText,
      completedArtifact,
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

  getActiveRun(): ActiveReviewRun | undefined {
    return this.activeRun;
  }

  currentPhaseFile(): WorkflowPhaseFile | undefined {
    if (!this.activeRun?.phaseInProgress) return undefined;
    const index = this.activeRun.nextPhaseIndex - 1;
    return index >= 0 ? this.activeRun.phases[index]?.file : undefined;
  }

  isReadOnlyPhase(): boolean {
    const phaseFile = this.currentPhaseFile();
    if (!phaseFile) return false;
    return Boolean(this.activeRun?.noFix) || isReadOnlyPhaseFile(phaseFile);
  }

  private validateActivePhaseSubmission(
    runId: string,
    phaseFile: string,
  ):
    | ({ ok: true; run: ActiveReviewRun } & Pick<
        RecordArtifactResult,
        "warnings"
      >)
    | { ok: false; reason: string; warnings: ReviewArtifactWarning[] } {
    const run = this.activeRun;
    if (!run?.phaseInProgress) {
      return {
        ok: false,
        reason: "No active /review phase is accepting artifacts.",
        warnings: [],
      };
    }

    const currentPhaseFile = this.currentPhaseFile();
    const warnings: ReviewArtifactWarning[] = [];
    if (run.id !== runId) {
      warnings.push({
        code: "run_mismatch",
        message: `Artifact runId ${runId} does not match active run ${run.id}.`,
      });
    }
    if (currentPhaseFile !== phaseFile) {
      warnings.push({
        code: "phase_mismatch",
        message: `Artifact phaseFile ${phaseFile} does not match active phase ${currentPhaseFile}.`,
      });
    }

    if (warnings.length > 0) {
      return {
        ok: false,
        reason: warnings.map((warning) => warning.message).join(" "),
        warnings,
      };
    }

    return { ok: true, run, warnings };
  }
}

function emptyPendingArtifact(): PendingPhaseArtifactState {
  return { patches: [], warnings: [] };
}

function parseReviewControl(
  text: string | undefined,
): ReviewControl | undefined {
  if (!text) return undefined;

  const match = text.match(
    /<review_control>\s*([\s\S]*?)\s*<\/review_control>/,
  );
  if (!match?.[1]) return undefined;

  try {
    const parsed = JSON.parse(match[1]) as ReviewControl;
    return parsed && typeof parsed === "object" ? parsed : undefined;
  } catch {
    return undefined;
  }
}

function findPhaseIndex(
  run: ActiveReviewRun,
  phaseFile: WorkflowPhaseFile,
): number {
  const index = run.phases.findIndex((phase) => phase.file === phaseFile);
  if (index < 0)
    throw new Error(`Workflow phase not found in run: ${phaseFile}`);
  return index;
}

function decideNextPhaseIndex(
  run: ActiveReviewRun,
  completedPhaseIndex: number,
  latestAssistantText: string | undefined,
  completedArtifact: PhaseArtifactStatus | undefined,
): number | undefined {
  const completedPhaseFile = run.phases[completedPhaseIndex]?.file;

  if (completedPhaseFile === GAPFILL_PHASE_FILE) {
    const control = parseReviewControl(latestAssistantText);
    const hasNewHuntTasks = completedArtifact?.artifact
      ? hasMaterialNextTasks(completedArtifact)
      : Array.isArray(control?.new_hunt_tasks) &&
        control.new_hunt_tasks.length > 0;

    if (hasNewHuntTasks && run.gapfillLoopCount < MAX_GAPFILL_LOOPS) {
      run.gapfillLoopCount += 1;
      return findPhaseIndex(run, HUNT_PHASE_FILE);
    }

    return findPhaseIndex(run, DEDUPE_PHASE_FILE);
  }

  const next = completedPhaseIndex + 1;
  return next < run.phases.length ? next : undefined;
}
