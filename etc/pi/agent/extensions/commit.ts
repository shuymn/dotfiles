import { readFileSync } from "node:fs";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { getSelectListTheme, isToolCallEventType } from "@earendil-works/pi-coding-agent";
import { fuzzyFilter, Key, matchesKey, SelectList, truncateToWidth, type SelectItem } from "@earendil-works/pi-tui";

const COMMIT_INSTRUCTIONS = readFileSync(new URL("./commit-instructions.md", import.meta.url), "utf8");

type CommitLanguage = "auto" | "english" | "japanese";

type CommitOptions = {
  language: CommitLanguage;
  createBranch: boolean;
  baseBranch?: string;
};

const PROHIBITED_GIT_PATTERNS = [
  /(^|[;&|]\s*)git\s+restore\b/,
  /(^|[;&|]\s*)git\s+reset\b/,
  /(^|[;&|]\s*)git\s+checkout\s+(?:--|-f\b)/,
  /(^|[;&|]\s*)git\s+switch\b[^\n;|&]*\s--discard-changes\b/,
  /(^|[;&|]\s*)git\s+clean\b/,
];

function isPrintableInput(data: string): boolean {
  return data.length > 0 && !data.startsWith("\x1b") && !data.startsWith("\x7f") && !data.startsWith("\r");
}

async function selectFuzzy(
  ctx: ExtensionContext,
  title: string,
  items: SelectItem[],
  initialValue?: string,
): Promise<string | null> {
  return await ctx.ui.custom<string | null>((tui, theme, _keybindings, done) => {
    let query = "";
    let filteredItems = items;
    let list: SelectList;

    const makeList = () => {
      filteredItems = query.trim() ? fuzzyFilter(items, query.trim(), (item) => `${item.label} ${item.value} ${item.description ?? ""}`) : items;
      list = new SelectList(filteredItems, Math.min(Math.max(filteredItems.length, 1), 12), getSelectListTheme());
      const initialIndex = filteredItems.findIndex((item) => item.value === initialValue);
      if (initialIndex >= 0) list.setSelectedIndex(initialIndex);
      list.onSelect = (item) => done(item.value);
      list.onCancel = () => done(null);
    };

    makeList();

    return {
      invalidate: () => list.invalidate(),
      render: (width: number) => {
        const border = theme.fg("accent", "─".repeat(Math.max(0, width)));
        return [
          border,
          theme.fg("accent", theme.bold(title)),
          theme.fg("dim", `query: ${query || "(type to fuzzy-find)"}`),
          ...list.render(width),
          truncateToWidth(theme.fg("dim", "type search • ↑↓ navigate • enter select • esc cancel"), width, ""),
          border,
        ].map((line) => truncateToWidth(line, width, ""));
      },
      handleInput: (data: string) => {
        if (matchesKey(data, Key.backspace)) {
          query = query.slice(0, -1);
          makeList();
          tui.requestRender();
          return;
        }
        if (matchesKey(data, Key.escape)) {
          done(null);
          return;
        }
        if (isPrintableInput(data)) {
          query += data;
          makeList();
          tui.requestRender();
          return;
        }
        list.handleInput(data);
        tui.requestRender();
      },
    };
  });
}

async function getDefaultBranch(pi: ExtensionAPI): Promise<string | undefined> {
  const symbolic = await pi.exec("git", ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], { timeout: 3000 }).catch(() => undefined);
  if (symbolic?.code === 0) return symbolic.stdout.trim().replace(/^origin\//, "") || undefined;

  for (const candidate of ["main", "master"]) {
    const exists = await pi.exec("git", ["show-ref", "--verify", "--quiet", `refs/heads/${candidate}`], { timeout: 3000 }).catch(() => undefined);
    if (exists?.code === 0) return candidate;
  }

  return undefined;
}

async function getBranches(pi: ExtensionAPI, defaultBranch?: string): Promise<SelectItem[]> {
  const result = await pi
    .exec("git", ["for-each-ref", "--format=%(refname)%09%(refname:short)", "refs/heads", "refs/remotes"], { timeout: 5000 })
    .catch(() => undefined);

  const seen = new Set<string>();
  const branches = (result?.stdout ?? "")
    .split("\n")
    .map((line) => {
      const [refname, shortName] = line.trim().split("\t");
      return { refname, shortName };
    })
    .filter(({ refname, shortName }) => refname && shortName)
    .filter(({ refname }) => !refname.endsWith("/HEAD"))
    .map(({ shortName }) => shortName.replace(/^origin\//, ""))
    .filter((branch) => branch !== "origin")
    .filter((branch) => {
      if (seen.has(branch)) return false;
      seen.add(branch);
      return true;
    });

  const sorted = branches.sort((a, b) => {
    if (a === defaultBranch) return -1;
    if (b === defaultBranch) return 1;
    return a.localeCompare(b);
  });

  return sorted.map((branch) => ({
    value: branch,
    label: branch,
    description: branch === defaultBranch ? "default branch" : undefined,
  }));
}

async function collectCommitOptions(pi: ExtensionAPI, ctx: ExtensionContext): Promise<CommitOptions | null> {
  const language = (await selectFuzzy(
    ctx,
    "Commit message language",
    [
      { value: "auto", label: "Auto", description: "match recent commit history; ask if unclear" },
      { value: "english", label: "English", description: "equivalent to --english" },
      { value: "japanese", label: "Japanese", description: "equivalent to --japanese" },
    ],
    "auto",
  )) as CommitLanguage | null;
  if (!language) return null;

  const branchMode = await selectFuzzy(
    ctx,
    "Create a new branch first?",
    [
      { value: "no", label: "No", description: "commit on the current branch" },
      { value: "yes", label: "Yes", description: "create a generated branch before committing" },
    ],
    "no",
  );
  if (!branchMode) return null;

  if (branchMode === "no") return { language, createBranch: false };

  const defaultBranch = await getDefaultBranch(pi);
  const branches = await getBranches(pi, defaultBranch);
  const baseBranch = await selectFuzzy(
    ctx,
    "Base branch for the new branch",
    branches.length > 0 ? branches : [{ value: defaultBranch ?? "main", label: defaultBranch ?? "main", description: "fallback" }],
    defaultBranch,
  );
  if (!baseBranch) return null;

  return { language, createBranch: true, baseBranch };
}

function optionsForPrompt(options: CommitOptions): string {
  const flags: string[] = [];
  if (options.language === "english") flags.push("--english");
  if (options.language === "japanese") flags.push("--japanese");
  if (options.createBranch) {
    flags.push("--branch");
    if (options.baseBranch) flags.push(`--base=${options.baseBranch}`);
  }
  return flags.join(" ") || "(none)";
}

async function gitSnapshot(pi: ExtensionAPI): Promise<string> {
  const commands: Array<[label: string, args: string[]]> = [
    ["Status", ["status", "--short"]],
    ["Branch", ["branch", "--show-current"]],
    ["Recent", ["log", "--oneline", "-10"]],
    ["Unstaged", ["diff", "--stat"]],
    ["Staged", ["diff", "--cached", "--stat"]],
  ];

  const results = await Promise.all(
    commands.map(async ([label, args]) => {
      const result = await pi.exec("git", args, { timeout: 5000 }).catch((error: unknown) => ({
        code: 1,
        stdout: "",
        stderr: error instanceof Error ? error.message : String(error),
      }));
      const output = `${result.stdout}${result.stderr ? `\n${result.stderr}` : ""}`.trim();
      return `### ${label}\n${output || "(empty)"}`;
    }),
  );

  return results.join("\n\n");
}

export default function (pi: ExtensionAPI) {
  let commitWorkflowActive = false;
  let startupCommitLaunched = false;

  pi.registerFlag("commit", {
    description: "Start pi by opening the interactive /commit workflow",
    type: "boolean",
    default: false,
  });

  const startCommitWorkflow = async (ctx: ExtensionContext, notes: string, source: "command" | "flag") => {
    if (!ctx.isIdle()) {
      ctx.ui.notify("Agent is busy. Run /commit again after the current turn finishes.", "warning");
      return;
    }

    if (!ctx.hasUI) {
      ctx.ui.notify("/commit requires interactive UI", "warning");
      return;
    }

    const options = await collectCommitOptions(pi, ctx);
    if (!options) {
      ctx.ui.notify("/commit cancelled", "info");
      return;
    }

    commitWorkflowActive = true;
    const snapshot = await gitSnapshot(pi);
    const selectedOptions = optionsForPrompt(options);
    pi.sendUserMessage(
      `User invoked /commit via ${source} with interactive options: ${selectedOptions}\n\n${COMMIT_INSTRUCTIONS}\n\n## Interactive Options\n\n${selectedOptions}\n\n## Additional User Notes\n\n${
        notes.trim() || "(none)"
      }\n\n## Initial Git Snapshot (may be stale; verify with live commands)\n\n${snapshot}`,
    );
  };

  pi.on("session_start", async (event, ctx) => {
    if (event.reason !== "startup" || startupCommitLaunched || pi.getFlag("commit") !== true) return;
    startupCommitLaunched = true;
    await startCommitWorkflow(ctx, "", "flag");
  });

  pi.registerCommand("commit", {
    description: "Interactively create local git commits in meaningful units.",
    handler: async (args, ctx) => {
      await startCommitWorkflow(ctx, args, "command");
    },
  });

  pi.on("tool_call", async (event) => {
    if (!commitWorkflowActive) return undefined;
    if (!isToolCallEventType("bash", event)) return undefined;

    const command = event.input.command;
    if (PROHIBITED_GIT_PATTERNS.some((pattern) => pattern.test(command))) {
      return {
        block: true,
        reason:
          "Blocked by /commit extension: destructive git cleanup/reset commands are prohibited during commit preparation. Ask the user for explicit direction instead.",
      };
    }

    if (/(^|[;&|]\s*)git\s+push\b/.test(command)) {
      return { block: true, reason: "Blocked by /commit extension: /commit creates local commits only; do not push." };
    }

    return undefined;
  });

  pi.on("agent_end", async () => {
    commitWorkflowActive = false;
  });
}
