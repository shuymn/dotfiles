import { stat } from "node:fs/promises";
import { join } from "node:path";
import type { ExtensionAPI, ExtensionCommandContext } from "@earendil-works/pi-coding-agent";

const COMMAND_NAME = "simplify";
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

function parseArgs(args: string): SimplifyOptions {
  const files: string[] = [];
  let staged = false;

  for (const token of args.trim().split(/\s+/).filter(Boolean)) {
    if (token === "--staged" || token === "--cached") {
      staged = true;
    } else {
      files.push(token.replace(/^@/, ""));
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
    const path = status.startsWith("R") || status.startsWith("C") ? parts[2] : parts[1];
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

async function execGit(pi: ExtensionAPI, cwd: string, args: string[]) {
  return pi.exec("git", args, { cwd, timeout: 10_000 });
}

async function getRecentTrackedFiles(pi: ExtensionAPI, cwd: string): Promise<Target[]> {
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
    .filter((candidate): candidate is { path: string; mtimeMs: number } => Boolean(candidate))
    .sort((a, b) => b.mtimeMs - a.mtimeMs)
    .slice(0, RECENT_FILE_LIMIT)
    .map((candidate) => ({ path: candidate.path, status: "recent", source: "recent" as const }));
}

async function collectTargets(pi: ExtensionAPI, cwd: string, options: SimplifyOptions): Promise<Target[]> {
  if (options.files.length > 0) {
    return options.files.map((path) => ({ path, status: "explicit", source: "explicit" as const }));
  }

  const unstagedArgs = ["diff", "--name-status"];
  const stagedArgs = ["diff", "--cached", "--name-status"];
  const targets: Target[] = [];

  if (options.staged) {
    const staged = await execGit(pi, cwd, stagedArgs);
    if (staged.code === 0) targets.push(...parseNameStatus(staged.stdout, "diff"));
  } else {
    const [unstaged, staged, status] = await Promise.all([
      execGit(pi, cwd, unstagedArgs),
      execGit(pi, cwd, stagedArgs),
      execGit(pi, cwd, ["status", "--porcelain"]),
    ]);

    if (unstaged.code === 0) targets.push(...parseNameStatus(unstaged.stdout, "diff"));
    if (staged.code === 0) targets.push(...parseNameStatus(staged.stdout, "diff"));

    if (status.code === 0) {
      for (const line of status.stdout.split("\n")) {
        if (!line.startsWith("?? ")) continue;
        targets.push({ path: line.slice(3).trim(), status: "untracked", source: "diff" });
      }
    }
  }

  const unique = uniqueTargets(targets);
  return unique.length > 0 ? unique : getRecentTrackedFiles(pi, cwd);
}

async function collectDiff(pi: ExtensionAPI, cwd: string, options: SimplifyOptions, targets: Target[]): Promise<string> {
  if (targets.every((target) => target.source === "recent")) return "";

  const paths = options.files.length > 0 ? ["--", ...options.files] : [];
  const chunks: string[] = [];

  if (options.staged) {
    const staged = await execGit(pi, cwd, ["diff", "--cached", ...paths]);
    if (staged.code === 0 && staged.stdout.trim()) chunks.push(`## Staged diff\n\n${staged.stdout}`);
  } else {
    const [unstaged, staged] = await Promise.all([
      execGit(pi, cwd, ["diff", ...paths]),
      execGit(pi, cwd, ["diff", "--cached", ...paths]),
    ]);

    if (unstaged.code === 0 && unstaged.stdout.trim()) chunks.push(`## Unstaged diff\n\n${unstaged.stdout}`);
    if (staged.code === 0 && staged.stdout.trim()) chunks.push(`## Staged diff\n\n${staged.stdout}`);
  }

  return truncate(chunks.join("\n\n"), MAX_DIFF_CHARS);
}

function buildReviewPrompt(kind: "reuse" | "quality" | "efficiency", targetList: string): string {
  const shared = `You are one reviewer in a /simplify command. Review only; do not edit files.\n\nScope:\n${targetList}\n\nInspect the target files and use git diff/status as needed to focus on the recent changes.\n\nReturn concise, actionable findings. For every finding include: file/path, exact issue, why it matters, and suggested fix. If nothing worth changing, say so. Avoid speculative or stylistic-only findings.`;

  if (kind === "reuse") {
    return `${shared}\n\nFocus: code reuse. Look for newly written logic that should use existing project utilities/components/constants, duplicated functions from elsewhere, unnecessary bespoke helpers, and missed abstractions already present in the codebase.`;
  }

  if (kind === "quality") {
    return `${shared}\n\nFocus: code quality simplification. Look for redundant state, needless branching/nesting, copy-paste variants, hard-coded strings where constants/types already exist, unclear names, unnecessary comments, over-clever code, and opportunities to make the changed code clearer while preserving behavior.`;
  }

  return `${shared}\n\nFocus: efficiency. Look for unnecessary computation/API/database calls, serial work that can safely be parallelized, full collection fetches when one item/count is enough, repeated parsing/allocation in hot paths, and waste introduced by the change. Only flag issues with practical impact.`;
}

function buildSimplifyPrompt(targets: Target[], diff: string): string {
  const targetList = targets.map((target) => `- ${target.path} (${target.status}; ${target.source})`).join("\n");
  const quotedTargets = targets.map((target) => shellQuote(target.path)).join(" ");

  return `Run a Claude Code-style /simplify pass for the current repository.\n\nPhase 1 is already prepared by the extension. Target files:\n${targetList}\n\nDiff context:\n\n${diff || "[No git diff available for these targets; inspect the listed files directly.]"}\n\nImportant rules:\n- Preserve exact behavior and public APIs unless a change is unquestionably internal and behavior-preserving.\n- Only modify target files unless a verified simplification requires a tiny adjacent change; explain any out-of-scope edit first.\n- Prefer readable, explicit code over clever line-count reduction.\n- Follow AGENTS.md/CLAUDE.md and existing project style.\n- Skip false positives. Do not make speculative changes.\n- Write the final response to the user in Japanese.\n\nPhase 2: spawn three subagents in parallel using spawn_subagent, one per review area. Use these exact delegated tasks:\n\n1. Code reuse review:\n${buildReviewPrompt("reuse", targetList)}\n\n2. Code quality review:\n${buildReviewPrompt("quality", targetList)}\n\n3. Efficiency review:\n${buildReviewPrompt("efficiency", targetList)}\n\nPhase 3: integrate the three review results. Directly apply only verified, behavior-preserving simplifications with read/edit/write/bash. If a finding is false positive or too risky, skip it. After editing, run the narrowest relevant formatter/test/typecheck/lint if discoverable. Summarize:\n- what changed\n- which subagent findings were applied\n- which findings were skipped and why\n\nFor quick inspection, target file shell arguments are: ${quotedTargets}`;
}

export default function (pi: ExtensionAPI): void {
  pi.registerCommand(COMMAND_NAME, {
    description: "Simplify recently changed code using three parallel subagent reviews",
    handler: async (args: string, ctx: ExtensionCommandContext) => {
      await ctx.waitForIdle();

      const options = parseArgs(args);
      const targets = await collectTargets(pi, ctx.cwd, options);
      if (targets.length === 0) {
        ctx.ui.notify("/simplify: no changed or recent files found.", "info");
        return;
      }

      const diff = await collectDiff(pi, ctx.cwd, options, targets);
      const prompt = buildSimplifyPrompt(targets, diff);

      ctx.ui.notify(`/simplify: queued review for ${targets.length} file(s).`, "info");
      pi.sendUserMessage(prompt, { deliverAs: "followUp" });
    },
  });
}
