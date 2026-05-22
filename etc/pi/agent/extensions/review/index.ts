import { lstat, open, readFile, readlink } from "node:fs/promises";
import { join } from "node:path";
import type {
  ExtensionAPI,
  ExtensionCommandContext,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { parseCommandArgs } from "../lib/command-args";
import {
  collectChangedTargets,
  type ExecGit,
  formatJsonTarget,
  isExplicitFileMode,
  normalizeFileArg,
  type Target,
  targetPathsForDiff,
  truncate,
} from "../lib/git";
import { getLatestAssistantMessageText } from "../lib/session-messages";
import { notifyIfUI } from "../lib/tui";
import {
  REVIEW_WORKFLOW_EVENT_NAME,
  type ReviewWorkflowLifecycleEvent,
  type ReviewWorkflowLifecycleStatus,
  reviewWorkflowEventName,
} from "./events";
import { loadWorkflowPhases } from "./phases";
import { buildPhasePrompt } from "./prompts";
import { clearReviewWidget, refreshReviewWidget } from "./widget";
import {
  type ActiveReviewRun,
  type QueuedPhase,
  type ReviewRunSeed,
  ReviewWorkflowController,
} from "./workflow";

const COMMAND_NAME = "review";
const TOOL_NAME = "review";
const MAX_DIFF_CHARS = 80_000;
const MAX_UNTRACKED_FILE_CHARS = 20_000;
const MAX_PHASE_NOTE_CHARS = 20_000;
const INVESTIGATION_ALLOWED_TOOLS = new Set([
  "read",
  "grep",
  "find",
  "ls",
  "spawn_subagent",
  "get_subagent_result",
  "list_subagents",
  "tavily_search",
  "tavily_extract",
  "tavily_map",
  "tavily_crawl",
  "tavily_auth_status",
]);

export {
  REVIEW_WORKFLOW_EVENT_NAME,
  type ReviewWorkflowLifecycleEvent,
  type ReviewWorkflowLifecycleStatus,
  WORKFLOW_CANCELLED_EVENT,
  WORKFLOW_COMPLETED_EVENT,
  WORKFLOW_FAILED_EVENT,
  WORKFLOW_STARTED_EVENT,
} from "./events";

const workflow = new ReviewWorkflowController();
let runStarting = false;
let startupGeneration = 0;
let nextPhaseTimer: ReturnType<typeof setTimeout> | undefined;

type ReviewOptions = {
  files: string[];
  staged: boolean;
  noFix: boolean;
  instructions: string;
};

function parseArgs(args: string): ReviewOptions {
  const parsed = parseCommandArgs({
    args,
    booleanFlags: ["--staged", "--cached", "--no-fix"] as const,
  });

  return {
    files: parsed.files,
    staged: parsed.flags["--staged"] || parsed.flags["--cached"],
    noFix: parsed.flags["--no-fix"],
    instructions: parsed.instructions,
  };
}

function formatPathForPrompt(path: string): string {
  return JSON.stringify(path);
}

function makeExecGit(pi: ExtensionAPI, cwd: string): ExecGit {
  return (args) => pi.exec("git", args, { cwd, timeout: 10_000 });
}

async function collectTargets(
  pi: ExtensionAPI,
  cwd: string,
  options: ReviewOptions,
): Promise<Target[]> {
  return collectChangedTargets(makeExecGit(pi, cwd), {
    files: options.files,
    staged: options.staged,
    preserveOldPath: true,
  });
}

async function readTextPrefix(path: string, maxChars: number): Promise<string> {
  const file = await open(path, "r");
  try {
    const buffer = Buffer.alloc(maxChars + 1);
    const { bytesRead } = await file.read(buffer, 0, buffer.length, 0);
    const text = buffer.subarray(0, bytesRead).toString("utf8");
    return bytesRead > maxChars ? truncate(text, maxChars) : text;
  } finally {
    await file.close();
  }
}

async function collectUntrackedFileChunk(
  cwd: string,
  target: Target,
): Promise<string | undefined> {
  if (target.status !== "untracked") return undefined;

  try {
    const absolutePath = join(cwd, target.path);
    const info = await lstat(absolutePath);
    const heading = `## Untracked file: ${formatPathForPrompt(target.path)}`;

    if (info.isSymbolicLink()) {
      const linkTarget = await readlink(absolutePath);
      return `${heading}\n\n[Skipped symlink -> ${formatPathForPrompt(linkTarget)}]`;
    }

    const content =
      info.size > MAX_UNTRACKED_FILE_CHARS
        ? await readTextPrefix(absolutePath, MAX_UNTRACKED_FILE_CHARS)
        : await readFile(absolutePath, "utf8");
    if (content.includes("\0")) {
      return `${heading}\n\n[Skipped binary-looking file content]`;
    }

    return `${heading}\n\n${truncate(content, MAX_UNTRACKED_FILE_CHARS)}`;
  } catch (error) {
    return `## Untracked file: ${formatPathForPrompt(target.path)}\n\n[Could not read file: ${error instanceof Error ? error.message : String(error)}]`;
  }
}

async function collectDiff(
  pi: ExtensionAPI,
  cwd: string,
  options: ReviewOptions,
  targets: Target[],
): Promise<string> {
  if (isExplicitFileMode(targets)) return "";

  const chunks: string[] = [];
  const execGit = makeExecGit(pi, cwd);
  const addDiffChunk = (
    label: string,
    result: Awaited<ReturnType<ExecGit>>,
  ) => {
    if (result.code === 0 && result.stdout.trim())
      chunks.push(`## ${label}\n\n${result.stdout}`);
  };

  const trackedPaths = targetPathsForDiff(targets);

  if (trackedPaths.length > 0) {
    if (options.staged) {
      addDiffChunk(
        "Staged diff",
        await execGit(["diff", "--cached", "--", ...trackedPaths]),
      );
    } else {
      addDiffChunk(
        "Combined diff against HEAD",
        await execGit(["diff", "HEAD", "--", ...trackedPaths]),
      );
    }
  }

  const untrackedChunks = await Promise.all(
    targets
      .filter((target) => target.status === "untracked")
      .map((target) => collectUntrackedFileChunk(cwd, target)),
  );
  chunks.push(
    ...untrackedChunks.filter((chunk): chunk is string => Boolean(chunk)),
  );

  return truncate(chunks.join("\n\n"), MAX_DIFF_CHARS);
}

async function createReviewRun(
  pi: ExtensionAPI,
  cwd: string,
  options: ReviewOptions,
): Promise<ReviewRunSeed | undefined> {
  const targets = await collectTargets(pi, cwd, options);
  if (targets.length === 0) return undefined;

  const [diff, phases] = await Promise.all([
    collectDiff(pi, cwd, options, targets),
    loadWorkflowPhases(options.noFix),
  ]);

  return {
    id: `${Date.now()}`,
    cwd,
    targets,
    diff,
    phases,
    noFix: options.noFix,
    instructions: options.instructions,
  };
}

type ReviewRunCreationResult =
  | { kind: "ready"; run: ReviewRunSeed }
  | { kind: "empty" }
  | { kind: "cancelled" };

async function createReviewRunWithStartGuard(
  pi: ExtensionAPI,
  cwd: string,
  options: ReviewOptions,
): Promise<ReviewRunCreationResult> {
  runStarting = true;
  startupGeneration += 1;
  const generation = startupGeneration;
  try {
    const run = await createReviewRun(pi, cwd, options);
    if (startupGeneration !== generation) return { kind: "cancelled" };
    if (!run) {
      runStarting = false;
      return { kind: "empty" };
    }
    return { kind: "ready", run };
  } catch (error) {
    if (startupGeneration === generation) runStarting = false;
    throw error;
  }
}

function clearQueuedPhaseTimer(): void {
  if (!nextPhaseTimer) return;
  clearTimeout(nextPhaseTimer);
  nextPhaseTimer = undefined;
}

function activeRun(): ActiveReviewRun | undefined {
  return workflow.getActiveRun();
}

function clearActiveRun(ctx?: Pick<ExtensionContext, "ui">): void {
  clearQueuedPhaseTimer();
  workflow.cancel();
  startupGeneration += 1;
  runStarting = false;
  if (ctx) clearReviewWidget(ctx);
}

function setPhaseWidget(
  ctx: Pick<ExtensionContext, "ui">,
  state: "queued" | "running",
  phaseNumber: number,
): void {
  const run = activeRun();
  if (!run) return;
  refreshReviewWidget(ctx, run, state, phaseNumber);
}

function emitWorkflowLifecycleEvent(
  pi: ExtensionAPI,
  status: ReviewWorkflowLifecycleStatus,
  run: ReviewRunSeed,
  extra: Pick<ReviewWorkflowLifecycleEvent, "reason" | "error"> = {},
): void {
  const event: ReviewWorkflowLifecycleEvent = {
    name: REVIEW_WORKFLOW_EVENT_NAME,
    status,
    runId: run.id,
    cwd: run.cwd,
    targets: run.targets,
    phaseCount: run.phases.length,
    noFix: run.noFix,
    ...extra,
  };

  try {
    pi.events.emit(reviewWorkflowEventName(status), event);
  } catch {
    // Lifecycle observers must not affect the review workflow itself.
  }
}

function failActiveRun(
  pi: ExtensionAPI,
  ctx: Pick<ExtensionContext, "ui">,
  message: string,
  error: unknown,
): void {
  const run = activeRun();
  if (run) {
    emitWorkflowLifecycleEvent(pi, "failed", run, {
      error: error instanceof Error ? error.message : String(error),
    });
  }
  clearActiveRun(ctx);
  notifyIfUI(ctx, message, "error");
}

function sendQueuedPhase(
  pi: ExtensionAPI,
  queued: QueuedPhase,
  ctx?: Pick<ExtensionContext, "ui">,
): void {
  if (ctx) setPhaseWidget(ctx, "running", queued.phaseIndex + 1);

  pi.sendMessage(
    {
      customType: "review-command",
      content: buildPhasePrompt(queued.run, queued.phaseIndex),
      display: false,
      details: {
        runId: queued.run.id,
        phase: queued.phase.file,
        phaseIndex: queued.phaseIndex + 1,
        phaseCount: queued.run.phases.length,
      },
    },
    { triggerTurn: true },
  );
}

function startReviewRun(
  pi: ExtensionAPI,
  run: ReviewRunSeed,
  ctx: Pick<ExtensionContext, "ui">,
): ActiveReviewRun {
  runStarting = false;
  const queued = workflow.start(run);
  emitWorkflowLifecycleEvent(pi, "started", queued.run);
  try {
    sendQueuedPhase(pi, queued, ctx);
  } catch (error) {
    failActiveRun(
      pi,
      ctx,
      "/review: ワークフローの phase をキューに追加できませんでした。",
      error,
    );
    throw error;
  }
  return queued.run;
}

function queueNextPhaseAfterCurrentTurn(
  pi: ExtensionAPI,
  runId: string,
  ctx: Pick<ExtensionContext, "ui">,
): void {
  clearQueuedPhaseTimer();
  nextPhaseTimer = setTimeout(() => {
    nextPhaseTimer = undefined;
    if (activeRun()?.id !== runId) return;
    const queued = workflow.startQueuedPhase();
    if (!queued) return;
    try {
      sendQueuedPhase(pi, queued, ctx);
    } catch (error) {
      failActiveRun(
        pi,
        ctx,
        "/review: 次の phase をキューに追加できませんでした。",
        error,
      );
    }
  }, 0);
}

export default function (pi: ExtensionAPI): void {
  pi.on("tool_call", async (event) => {
    if (!workflow.isReadOnlyPhase()) return;

    if (!INVESTIGATION_ALLOWED_TOOLS.has(event.toolName)) {
      return {
        block: true,
        reason: activeRun()?.noFix
          ? "/review --no-fix mode is read-only. This tool is not allowed while producing a report."
          : "/review investigation phases are read-only. This tool is allowed only in Stage 7: Fix.",
      };
    }

    if (event.toolName === "spawn_subagent") {
      (event.input as { readOnly?: boolean }).readOnly = true;
    }
  });

  pi.on("agent_end", async (event, ctx) => {
    const completingRun = activeRun();
    if (!completingRun?.phaseInProgress) return;

    const latestAssistantText = getLatestAssistantMessageText(event.messages);
    const decision = workflow.completePhase({
      latestAssistantText,
      truncateNotes: (text) => truncate(text, MAX_PHASE_NOTE_CHARS),
    });
    if (!decision) return;

    if (decision.kind === "completed") {
      if (completingRun)
        emitWorkflowLifecycleEvent(pi, "completed", completingRun);
      clearQueuedPhaseTimer();
      runStarting = false;
      clearReviewWidget(ctx);
      notifyIfUI(
        ctx,
        `/review: ワークフロー ${decision.runId} が完了しました。`,
        "info",
      );
      return;
    }

    setPhaseWidget(ctx, "queued", decision.phaseIndex + 1);
    queueNextPhaseAfterCurrentTurn(pi, decision.run.id, ctx);
  });

  pi.on("session_shutdown", async (_event, ctx) => {
    const run = activeRun();
    if (run)
      emitWorkflowLifecycleEvent(pi, "cancelled", run, {
        reason: "session_shutdown",
      });
    clearActiveRun(ctx);
  });

  pi.registerCommand(COMMAND_NAME, {
    description:
      "Run a multi-stage code review workflow and apply verified fixes, or report only with --no-fix",
    handler: async (args: string, ctx: ExtensionCommandContext) => {
      await ctx.waitForIdle();

      const trimmedArgs = args.trim();
      if (trimmedArgs === "cancel" || trimmedArgs === "--cancel") {
        const run = activeRun();
        const runId = run?.id;
        if (run)
          emitWorkflowLifecycleEvent(pi, "cancelled", run, {
            reason: "user_cancelled",
          });
        clearActiveRun(ctx);
        ctx.ui.notify(
          runId
            ? `/review: ワークフロー ${runId} をキャンセルしました。`
            : "/review: キャンセルできるワークフローがありません。",
          "info",
        );
        return;
      }

      if (activeRun() || runStarting) {
        ctx.ui.notify(
          "/review: 別のレビューワークフローが既に実行中です。",
          "warning",
        );
        return;
      }

      const options = parseArgs(args);
      const creation = await createReviewRunWithStartGuard(
        pi,
        ctx.cwd,
        options,
      );
      if (creation.kind === "cancelled") return;
      if (creation.kind === "empty") {
        ctx.ui.notify(
          "/review: 変更ファイルが見つかりませんでした。ファイル全体をレビューするにはパスを明示してください。",
          "info",
        );
        return;
      }

      const active = startReviewRun(pi, creation.run, ctx);
      ctx.ui.notify(
        `/review: ${active.targets.length} 件のファイルについて phase 1/${active.phases.length} をキューに追加しました。`,
        "info",
      );
    },
  });

  pi.registerTool({
    name: TOOL_NAME,
    label: "Review",
    description:
      "Queue a multi-stage code review workflow for changed, staged, or explicitly listed files, then apply verified fixes or produce a no-fix report.",
    promptSnippet:
      "Queue a /review pass that runs Recon, Hunt, Validate, Gapfill, Dedupe, Trace, Fix, and Verify stages before applying only validated fixes. Set noFix to produce a consolidated report without fixes.",
    promptGuidelines: [
      "Use review when the user asks for a code review workflow that should identify actionable issues, verify them, fix the valid ones, and run relevant checks.",
      "Use review with explicit files when the user names file paths; otherwise let review target current git changes. Use staged when the user specifically asks to review staged/cached changes.",
      "Use noFix when the user asks to report findings without fixing or editing files.",
    ],
    parameters: Type.Object({
      files: Type.Optional(
        Type.Array(
          Type.String({
            description: "File path to review as a whole-file target.",
          }),
          {
            description:
              "Explicit file paths to review. Omit to use git changes.",
          },
        ),
      ),
      staged: Type.Optional(
        Type.Boolean({
          description:
            "When true and files is omitted, review only staged/cached git changes.",
        }),
      ),
      noFix: Type.Optional(
        Type.Boolean({
          description:
            "When true, report validated review findings without applying fixes or editing files.",
        }),
      ),
      instructions: Type.Optional(
        Type.String({
          description: "Additional user instructions for this review pass.",
        }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      if (activeRun() || runStarting) {
        return {
          content: [
            {
              type: "text",
              text: "Another review workflow is already running.",
            },
          ],
          details: { activeRunId: activeRun()?.id },
        };
      }

      const options: ReviewOptions = {
        files: params.files?.map(normalizeFileArg) ?? [],
        staged: params.staged ?? false,
        noFix: params.noFix ?? false,
        instructions: params.instructions?.trim() ?? "",
      };
      const creation = await createReviewRunWithStartGuard(
        pi,
        ctx.cwd,
        options,
      );

      if (creation.kind === "cancelled") {
        return {
          content: [{ type: "text", text: "Review startup was cancelled." }],
          details: { targets: [] },
        };
      }

      if (creation.kind === "empty") {
        return {
          content: [
            {
              type: "text",
              text: "No changed files found for review. Pass explicit files to review whole files.",
            },
          ],
          details: { targets: [] },
        };
      }

      const active = startReviewRun(pi, creation.run, ctx);
      return {
        content: [
          {
            type: "text",
            text: `Queued review workflow ${active.id} phase 1/${active.phases.length} for ${active.targets.length} file(s):\n${active.targets
              .map(formatJsonTarget)
              .join("\n")}`,
          },
        ],
        details: { runId: active.id, targets: active.targets },
      };
    },
  });
}
