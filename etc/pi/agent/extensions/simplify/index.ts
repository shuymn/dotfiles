import { stat } from "node:fs/promises";
import { join } from "node:path";
import type {
  ExtensionAPI,
  ExtensionCommandContext,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const COMMAND_NAME = "simplify";
const TOOL_NAME = "simplify";
const MAX_DIFF_CHARS = 60_000;
const RECENT_FILE_LIMIT = 8;

type SimplifyOptions = {
  files: string[];
  staged: boolean;
};

type Target = {
  path: string;
  status: string;
  source: "diff" | "explicit" | "recent";
};

function normalizeFileArg(file: string): string {
  return file.replace(/^@/, "");
}

function parseArgs(args: string): SimplifyOptions {
  const files: string[] = [];
  let staged = false;

  for (const token of args.trim().split(/\s+/).filter(Boolean)) {
    if (token === "--staged" || token === "--cached") {
      staged = true;
    } else {
      files.push(normalizeFileArg(token));
    }
  }

  return { files, staged };
}

function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return `${text.slice(0, maxChars)}\n\n[diff truncated at ${maxChars} chars; inspect files directly before editing]`;
}

function shellQuote(value: string): string {
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

function parseNameStatus(stdout: string, source: Target["source"]): Target[] {
  const targets: Target[] = [];

  for (const line of stdout.split("\n")) {
    if (!line.trim()) continue;
    const parts = line.split("\t");
    const status = parts[0] ?? "modified";
    const path =
      status.startsWith("R") || status.startsWith("C") ? parts[2] : parts[1];
    if (path) targets.push({ path, status, source });
  }

  return targets;
}

function uniqueTargets(targets: Target[]): Target[] {
  const seen = new Set<string>();
  const result: Target[] = [];

  for (const target of targets) {
    if (seen.has(target.path)) continue;
    seen.add(target.path);
    result.push(target);
  }

  return result;
}

function formatTarget(target: Target): string {
  const details =
    target.status === target.source
      ? target.status
      : `${target.status}; ${target.source}`;
  return `- ${target.path} (${details})`;
}

function isExplicitFileMode(targets: Target[]): boolean {
  return (
    targets.length > 0 &&
    targets.every((target) => target.source === "explicit")
  );
}

async function execGit(pi: ExtensionAPI, cwd: string, args: string[]) {
  return pi.exec("git", args, { cwd, timeout: 10_000 });
}

async function getRecentTrackedFiles(
  pi: ExtensionAPI,
  cwd: string,
): Promise<Target[]> {
  const result = await execGit(pi, cwd, ["ls-files", "-z"]);
  if (result.code !== 0) return [];

  const candidates = await Promise.all(
    result.stdout
      .split("\0")
      .filter(Boolean)
      .map(async (path) => {
        try {
          const info = await stat(join(cwd, path));
          return { path, mtimeMs: info.mtimeMs };
        } catch {
          return undefined;
        }
      }),
  );

  return candidates
    .filter((candidate): candidate is { path: string; mtimeMs: number } =>
      Boolean(candidate),
    )
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
  if (options.files.length > 0) {
    return options.files.map((path) => ({
      path,
      status: "explicit",
      source: "explicit" as const,
    }));
  }

  const unstagedArgs = ["diff", "--name-status"];
  const stagedArgs = ["diff", "--cached", "--name-status"];
  const targets: Target[] = [];

  if (options.staged) {
    const staged = await execGit(pi, cwd, stagedArgs);
    if (staged.code === 0)
      targets.push(...parseNameStatus(staged.stdout, "diff"));
  } else {
    const [unstaged, staged, status] = await Promise.all([
      execGit(pi, cwd, unstagedArgs),
      execGit(pi, cwd, stagedArgs),
      execGit(pi, cwd, ["status", "--porcelain"]),
    ]);

    if (unstaged.code === 0)
      targets.push(...parseNameStatus(unstaged.stdout, "diff"));
    if (staged.code === 0)
      targets.push(...parseNameStatus(staged.stdout, "diff"));

    if (status.code === 0) {
      for (const line of status.stdout.split("\n")) {
        if (!line.startsWith("?? ")) continue;
        targets.push({
          path: line.slice(3).trim(),
          status: "untracked",
          source: "diff",
        });
      }
    }
  }

  const unique = uniqueTargets(targets);
  return unique.length > 0 ? unique : getRecentTrackedFiles(pi, cwd);
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
  const addDiffChunk = (
    label: string,
    result: Awaited<ReturnType<typeof execGit>>,
  ) => {
    if (result.code === 0 && result.stdout.trim())
      chunks.push(`## ${label}\n\n${result.stdout}`);
  };

  if (options.staged) {
    addDiffChunk("Staged diff", await execGit(pi, cwd, ["diff", "--cached"]));
  } else {
    const [unstaged, staged] = await Promise.all([
      execGit(pi, cwd, ["diff"]),
      execGit(pi, cwd, ["diff", "--cached"]),
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

function buildSimplifyPrompt(targets: Target[], diff: string): string {
  const targetList = targets.map(formatTarget).join("\n");
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

  return `Run a Claude Code-style /simplify pass for the current repository.\n\nPhase 1 is already prepared by the extension. Target files:\n${targetList}\n\nScope guidance:\n${scopeInstruction}\n\nDiff context:\n\n${diffContext}\n\nImportant rules:\n- Preserve exact behavior and public APIs unless a change is unquestionably internal and behavior-preserving.\n- Only modify target files unless a verified simplification requires a tiny adjacent change; explain any out-of-scope edit first.\n- Prefer readable, explicit code over clever line-count reduction.\n- Follow AGENTS.md/CLAUDE.md and existing project style.\n- Skip false positives. Do not make speculative changes.\n- Write the final response to the user in Japanese.\n\nPhase 2: spawn three subagents in parallel using spawn_subagent, one per review area. Use these exact delegated tasks:\n\n1. Code reuse review:\n${buildReviewPrompt("reuse", targetList, scopeInstruction)}\n\n2. Code quality review:\n${buildReviewPrompt("quality", targetList, scopeInstruction)}\n\n3. Efficiency review:\n${buildReviewPrompt("efficiency", targetList, scopeInstruction)}\n\nPhase 3: integrate the three review results. Directly apply only verified, behavior-preserving simplifications with read/edit/write/bash. If a finding is false positive or too risky, skip it. After editing, run the narrowest relevant formatter/test/typecheck/lint if discoverable. Summarize:\n- what changed\n- which subagent findings were applied\n- which findings were skipped and why\n\nFor quick inspection, target file shell arguments are: ${quotedTargets}`;
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
      content: buildSimplifyPrompt(targets, diff),
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
        ctx.ui.notify("/simplify: no changed or recent files found.", "info");
        return;
      }

      ctx.ui.notify(
        `/simplify: queued review for ${targets.length} file(s).`,
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
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const options: SimplifyOptions = {
        files: params.files?.map(normalizeFileArg) ?? [],
        staged: params.staged ?? false,
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
              .map(formatTarget)
              .join("\n")}`,
          },
        ],
        details: { targets },
      };
    },
  });
}
