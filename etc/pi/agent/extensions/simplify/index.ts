import { stat } from "node:fs/promises";
import { join } from "node:path";
import type {
  ExtensionAPI,
  ExtensionCommandContext,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { parseCommandArgs } from "../lib/command-args";
import {
  collectChangedTargets,
  type ExecGit,
  formatPlainTarget,
  isExplicitFileMode,
  normalizeFileArg,
  shellQuote,
  type Target,
  truncate,
} from "../lib/git";

const COMMAND_NAME = "simplify";
const TOOL_NAME = "simplify";
const MAX_DIFF_CHARS = 60_000;
const RECENT_FILE_LIMIT = 8;
const RECENT_FILE_STAT_CONCURRENCY = 64;

type SimplifyOptions = {
  files: string[];
  staged: boolean;
  instructions: string;
};

function parseArgs(args: string): SimplifyOptions {
  const parsed = parseCommandArgs({
    args,
    booleanFlags: ["--staged", "--cached"] as const,
  });

  return {
    files: parsed.files,
    staged: parsed.flags["--staged"] || parsed.flags["--cached"],
    instructions: parsed.instructions,
  };
}

function makeExecGit(pi: ExtensionAPI, cwd: string): ExecGit {
  return (args) => pi.exec("git", args, { cwd, timeout: 10_000 });
}

async function getRecentTrackedFiles(
  pi: ExtensionAPI,
  cwd: string,
): Promise<Target[]> {
  const result = await makeExecGit(pi, cwd)(["ls-files", "-z"]);
  if (result.code !== 0) return [];

  const paths = result.stdout.split("\0").filter(Boolean);
  const candidates: Array<{ path: string; mtimeMs: number }> = [];

  for (
    let index = 0;
    index < paths.length;
    index += RECENT_FILE_STAT_CONCURRENCY
  ) {
    const batch = paths.slice(index, index + RECENT_FILE_STAT_CONCURRENCY);
    const stats = await Promise.all(
      batch.map(async (path) => {
        try {
          const info = await stat(join(cwd, path));
          return { path, mtimeMs: info.mtimeMs };
        } catch {
          return undefined;
        }
      }),
    );
    candidates.push(
      ...stats.filter(
        (candidate): candidate is { path: string; mtimeMs: number } =>
          Boolean(candidate),
      ),
    );
  }

  return candidates
    .sort((a, b) => b.mtimeMs - a.mtimeMs)
    .slice(0, RECENT_FILE_LIMIT)
    .map((candidate) => ({
      path: candidate.path,
      status: "recent",
      source: "recent" as const,
    }));
}

async function collectTargets(
  pi: ExtensionAPI,
  cwd: string,
  options: SimplifyOptions,
): Promise<Target[]> {
  const targets = await collectChangedTargets(makeExecGit(pi, cwd), {
    files: options.files,
    staged: options.staged,
  });
  return targets.length > 0 ? targets : getRecentTrackedFiles(pi, cwd);
}

async function collectDiff(
  pi: ExtensionAPI,
  cwd: string,
  options: SimplifyOptions,
  targets: Target[],
): Promise<string> {
  if (
    isExplicitFileMode(targets) ||
    targets.every((target) => target.source === "recent")
  )
    return "";
  const chunks: string[] = [];
  const execGit = makeExecGit(pi, cwd);
  const addDiffChunk = (
    label: string,
    result: Awaited<ReturnType<ExecGit>>,
  ) => {
    if (result.code === 0 && result.stdout.trim())
      chunks.push(`## ${label}\n\n${result.stdout}`);
  };

  if (options.staged) {
    addDiffChunk("Staged diff", await execGit(["diff", "--cached"]));
  } else {
    const [unstaged, staged] = await Promise.all([
      execGit(["diff"]),
      execGit(["diff", "--cached"]),
    ]);

    addDiffChunk("Unstaged diff", unstaged);
    addDiffChunk("Staged diff", staged);
  }

  return truncate(chunks.join("\n\n"), MAX_DIFF_CHARS);
}

type ReviewKind = "reuse" | "quality" | "efficiency";

const REVIEW_FOCUS: Record<ReviewKind, string> = {
  reuse:
    "Focus: code reuse. Look for newly written logic that should use existing project utilities/components/constants, duplicated functions from elsewhere, unnecessary bespoke helpers, and missed abstractions already present in the codebase.",
  quality:
    "Focus: code quality simplification. Look for redundant state, needless branching/nesting, copy-paste variants, hard-coded strings where constants/types already exist, unclear names, unnecessary comments, over-clever code, and opportunities to make the changed code clearer while preserving behavior.",
  efficiency:
    "Focus: efficiency. Look for unnecessary computation/API/database calls, serial work that can safely be parallelized, full collection fetches when one item/count is enough, repeated parsing/allocation in hot paths, and waste introduced by the change. Only flag issues with practical impact.",
};

function buildReviewPrompt(
  kind: ReviewKind,
  targetList: string,
  scopeInstruction: string,
): string {
  const shared = `You are one reviewer in a /simplify command. Review only; do not edit files.\n\nScope:\n${targetList}\n\n${scopeInstruction}\n\nReturn concise, actionable findings. For every finding include: file/path, exact issue, why it matters, and suggested fix. If nothing worth changing, say so. Avoid speculative or stylistic-only findings.`;
  return `${shared}\n\n${REVIEW_FOCUS[kind]}`;
}

function buildSimplifyPrompt(
  targets: Target[],
  diff: string,
  instructions: string,
): string {
  const targetList = targets.map(formatPlainTarget).join("\n");
  const quotedTargets = targets
    .map((target) => shellQuote(target.path))
    .join(" ");
  const explicitFileMode = isExplicitFileMode(targets);
  const scopeInstruction = explicitFileMode
    ? "The user explicitly passed file path(s). Ignore repository git status/diffs for scope selection. Review each listed file as a whole-file target, and do not inspect unrelated changed files just because git status/diff shows them."
    : "Inspect the target files and use git diff/status as needed to focus on the recent changes.";
  const diffContext = explicitFileMode
    ? "[Explicit file mode: git diff is intentionally ignored; inspect the listed files directly as whole-file targets.]"
    : diff ||
      "[No git diff available for these targets; inspect the listed files directly.]";
  const scopeWithUserInstructions = instructions
    ? `${scopeInstruction}\n\nAdditional user instructions:\n${instructions}`
    : scopeInstruction;

  return `Run a Claude Code-style /simplify pass for the current repository.\n\nPhase 1 is already prepared by the extension. Target files:\n${targetList}\n\nScope guidance:\n${scopeWithUserInstructions}\n\nDiff context:\n\n${diffContext}\n\nImportant rules:\n- Preserve exact behavior and public APIs unless a change is unquestionably internal and behavior-preserving.\n- Only modify target files unless a verified simplification requires a tiny adjacent change; explain any out-of-scope edit first.\n- Prefer readable, explicit code over clever line-count reduction.\n- Follow AGENTS.md/CLAUDE.md and existing project style.\n- Skip false positives. Do not make speculative changes.\n- Write the final response to the user in Japanese.\n\nPhase 2: spawn three subagents in parallel using spawn_subagent, one per review area. Use these exact delegated tasks:\n\n1. Code reuse review:\n${buildReviewPrompt("reuse", targetList, scopeWithUserInstructions)}\n\n2. Code quality review:\n${buildReviewPrompt("quality", targetList, scopeWithUserInstructions)}\n\n3. Efficiency review:\n${buildReviewPrompt("efficiency", targetList, scopeWithUserInstructions)}\n\nPhase 3: integrate the three review results. Directly apply only verified, behavior-preserving simplifications with read/edit/write/bash. Apply only findings consistent with the Additional user instructions above; skip conflicting findings and explain why. If a finding is false positive or too risky, skip it. After editing, run the narrowest relevant formatter/test/typecheck/lint if discoverable. Summarize:\n- what changed\n- which subagent findings were applied\n- which findings were skipped and why\n\nFor quick inspection, target file shell arguments are: ${quotedTargets}`;
}

async function queueSimplifyPass(
  pi: ExtensionAPI,
  cwd: string,
  options: SimplifyOptions,
): Promise<Target[]> {
  const targets = await collectTargets(pi, cwd, options);
  if (targets.length === 0) return targets;

  const diff = await collectDiff(pi, cwd, options, targets);

  pi.sendMessage(
    {
      customType: "simplify-command",
      content: buildSimplifyPrompt(targets, diff, options.instructions),
      display: false,
    },
    { deliverAs: "followUp", triggerTurn: true },
  );

  return targets;
}

export default function (pi: ExtensionAPI): void {
  pi.registerCommand(COMMAND_NAME, {
    description:
      "Simplify recently changed code using three parallel subagent reviews",
    handler: async (args: string, ctx: ExtensionCommandContext) => {
      await ctx.waitForIdle();

      const options = parseArgs(args);
      const targets = await queueSimplifyPass(pi, ctx.cwd, options);
      if (targets.length === 0) {
        ctx.ui.notify(
          "/simplify: 変更または最近のファイルが見つかりませんでした。",
          "info",
        );
        return;
      }

      ctx.ui.notify(
        `/simplify: ${targets.length} 件のファイルのレビューをキューに追加しました。`,
        "info",
      );
    },
  });

  pi.registerTool({
    name: TOOL_NAME,
    label: "Simplify",
    description:
      "Queue a /simplify pass for changed, staged, recent, or explicitly listed files using three parallel subagent reviews.",
    promptSnippet:
      "Queue a /simplify pass that reviews target files with reuse, quality, and efficiency subagents, then applies verified simplifications.",
    promptGuidelines: [
      "Use simplify when the user asks to simplify, clean up, reduce duplication, improve code reuse, or optimize recently changed code while preserving behavior.",
      "Use simplify with explicit files when the user names file paths; otherwise let simplify target current git changes, or recent tracked files when there are no changes.",
    ],
    parameters: Type.Object({
      files: Type.Optional(
        Type.Array(
          Type.String({
            description: "File path to review as a whole-file target.",
          }),
          {
            description:
              "Explicit file paths to simplify. Omit to use git changes or recent files.",
          },
        ),
      ),
      staged: Type.Optional(
        Type.Boolean({
          description:
            "When true and files is omitted, review only staged/cached git changes.",
        }),
      ),
      instructions: Type.Optional(
        Type.String({
          description: "Additional user instructions for this simplify pass.",
        }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const options: SimplifyOptions = {
        files: params.files?.map(normalizeFileArg) ?? [],
        staged: params.staged ?? false,
        instructions: params.instructions?.trim() ?? "",
      };
      const targets = await queueSimplifyPass(pi, ctx.cwd, options);

      if (targets.length === 0) {
        return {
          content: [
            {
              type: "text",
              text: "No changed or recent files found for simplify.",
            },
          ],
          details: { targets: [] },
        };
      }

      return {
        content: [
          {
            type: "text",
            text: `Queued simplify review for ${targets.length} file(s):\n${targets
              .map(formatPlainTarget)
              .join("\n")}`,
          },
        ],
        details: { targets },
      };
    },
  });
}
