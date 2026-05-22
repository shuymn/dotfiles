import { readFileSync } from "node:fs";
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import type { SelectItem } from "@earendil-works/pi-tui";
import { formatAdditionalUserNotesBlock } from "../lib/prompt";
import { inputOptional, selectFuzzy } from "../lib/tui";
import {
  applyWorkflowActiveTools,
  evaluateWorkflowToolCall,
  registerWorkflowTempFileTool,
} from "../lib/workflow-tool-policy";

const COMMIT_INSTRUCTIONS = readFileSync(
  new URL("./commit-instructions.md", import.meta.url),
  "utf8",
);
const HUMAN_RESPONSE_LANGUAGE_INSTRUCTION = `## 人間向けレスポンスの言語

ユーザーへの返答・確認・エラー説明など、人間に見せるメッセージは日本語で書くこと。これは選択されたコミットメッセージ言語を変更しない。`;

type CommitLanguage = "auto" | "english" | "japanese";

type CommitOptions = {
  language: CommitLanguage;
  createBranch: boolean;
  baseBranch?: string;
  additionalNotes?: string;
};

async function getDefaultBranch(pi: ExtensionAPI): Promise<string | undefined> {
  const symbolic = await pi
    .exec(
      "git",
      ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
      {
        timeout: 3000,
      },
    )
    .catch(() => undefined);
  if (symbolic?.code === 0)
    return symbolic.stdout.trim().replace(/^origin\//, "") || undefined;

  for (const candidate of ["main", "master"]) {
    const exists = await pi
      .exec(
        "git",
        ["show-ref", "--verify", "--quiet", `refs/heads/${candidate}`],
        {
          timeout: 3000,
        },
      )
      .catch(() => undefined);
    if (exists?.code === 0) return candidate;
  }

  return undefined;
}

async function getBranches(
  pi: ExtensionAPI,
  defaultBranch?: string,
): Promise<SelectItem[]> {
  const result = await pi
    .exec(
      "git",
      [
        "for-each-ref",
        "--format=%(refname)%09%(refname:short)",
        "refs/heads",
        "refs/remotes",
      ],
      { timeout: 5000 },
    )
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
    description: branch === defaultBranch ? "デフォルトブランチ" : undefined,
  }));
}

async function collectAdditionalNotes(
  ctx: ExtensionContext,
): Promise<string | null | undefined> {
  return await inputOptional(ctx, {
    title: "追加指示",
    placeholder: "例: package-lock.json は無視してください。空 Enter でなし",
  });
}

async function collectCommitOptions(
  pi: ExtensionAPI,
  ctx: ExtensionContext,
): Promise<CommitOptions | null> {
  let step: "language" | "branchMode" | "baseBranch" | "additionalNotes" =
    "language";
  let language: CommitLanguage = "auto";
  let branchMode: "yes" | "no" = "no";
  let baseBranch: string | undefined;
  let defaultBranch: string | undefined;
  let branches: SelectItem[] | undefined;

  while (true) {
    if (step === "language") {
      const selectedLanguage = (await selectFuzzy(ctx, {
        title: "コミットメッセージの言語",
        items: [
          {
            value: "auto",
            label: "自動",
            description: "直近のコミット履歴に合わせる。不明なら確認する",
          },
          { value: "english", label: "英語", description: "--english 相当" },
          {
            value: "japanese",
            label: "日本語",
            description: "--japanese 相当",
          },
        ],
        initialValue: language,
      })) as CommitLanguage | null;
      if (!selectedLanguage) return null;
      language = selectedLanguage;
      step = "branchMode";
      continue;
    }

    if (step === "branchMode") {
      const selectedBranchMode = (await selectFuzzy(ctx, {
        title: "先に新しいブランチを作成しますか？",
        items: [
          {
            value: "no",
            label: "いいえ",
            description: "現在のブランチにコミットする",
          },
          {
            value: "yes",
            label: "はい",
            description: "コミット前に新しいブランチを作成する",
          },
        ],
        initialValue: branchMode,
      })) as "yes" | "no" | null;
      if (!selectedBranchMode) {
        step = "language";
        continue;
      }
      branchMode = selectedBranchMode;
      step = branchMode === "yes" ? "baseBranch" : "additionalNotes";
      continue;
    }

    if (step === "baseBranch") {
      if (!branches) {
        defaultBranch = await getDefaultBranch(pi);
        branches = await getBranches(pi, defaultBranch);
      }
      const selectedBaseBranch = await selectFuzzy(ctx, {
        title: "新しいブランチのベースブランチ",
        items:
          branches.length > 0
            ? branches
            : [
                {
                  value: defaultBranch ?? "main",
                  label: defaultBranch ?? "main",
                  description: "フォールバック",
                },
              ],
        initialValue: baseBranch ?? defaultBranch,
      });
      if (!selectedBaseBranch) {
        step = "branchMode";
        continue;
      }
      baseBranch = selectedBaseBranch;
      step = "additionalNotes";
      continue;
    }

    const additionalNotes = await collectAdditionalNotes(ctx);
    if (additionalNotes === null) {
      step = branchMode === "yes" ? "baseBranch" : "branchMode";
      continue;
    }

    return branchMode === "yes"
      ? { language, createBranch: true, baseBranch, additionalNotes }
      : { language, createBranch: false, additionalNotes };
  }
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

function escapeGitAuthorPattern(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function getGitConfigValue(
  pi: ExtensionAPI,
  key: string,
): Promise<string | undefined> {
  const result = await pi
    .exec("git", ["config", "--get", key], { timeout: 3000 })
    .catch(() => undefined);
  if (result?.code !== 0) return undefined;
  return result.stdout.trim() || undefined;
}

async function getSelfAuthorPattern(
  pi: ExtensionAPI,
): Promise<string | undefined> {
  const email = await getGitConfigValue(pi, "user.email");
  if (email) return escapeGitAuthorPattern(email);

  const name = await getGitConfigValue(pi, "user.name");
  if (name) return escapeGitAuthorPattern(name);

  return undefined;
}

async function gitSnapshot(pi: ExtensionAPI): Promise<string> {
  const selfAuthorPattern = await getSelfAuthorPattern(pi);
  const commands: Array<[label: string, args: string[]]> = [
    ["Status", ["status", "--short"]],
    ["Branch", ["branch", "--show-current"]],
  ];

  if (selfAuthorPattern) {
    commands.push([
      "Recent Self Commits (primary for auto language)",
      ["log", `--author=${selfAuthorPattern}`, "--format=%s", "-10"],
    ]);
  }

  commands.push(
    [
      "Recent All Commits (fallback for auto language)",
      ["log", "--format=%s", "-10"],
    ],
    ["Unstaged", ["diff", "--stat"]],
    ["Staged", ["diff", "--cached", "--stat"]],
  );

  const results = await Promise.all(
    commands.map(async ([label, args]) => {
      const result = await pi
        .exec("git", args, { timeout: 5000 })
        .catch((error: unknown) => ({
          code: 1,
          stdout: "",
          stderr: error instanceof Error ? error.message : String(error),
        }));
      const output =
        `${result.stdout}${result.stderr ? `\n${result.stderr}` : ""}`.trim();
      return `### ${label}\n${output || "(empty)"}`;
    }),
  );

  return results.join("\n\n");
}

export default function (pi: ExtensionAPI) {
  let commitWorkflowActive = false;
  let startupCommitLaunched = false;

  pi.registerFlag("commit", {
    description: "対話式の commit ワークフローを実行して pi を終了する",
    type: "boolean",
    default: false,
  });

  const notifyAndShutdown = (
    ctx: ExtensionContext,
    message: string,
    level: "info" | "warning",
  ) => {
    ctx.ui.notify(message, level);
    ctx.shutdown();
  };

  const startCommitWorkflow = async (ctx: ExtensionContext) => {
    if (!ctx.isIdle()) {
      notifyAndShutdown(
        ctx,
        "エージェントが処理中です。処理を終了します。",
        "warning",
      );
      return;
    }

    if (!ctx.hasUI) {
      notifyAndShutdown(ctx, "--commit には対話式 UI が必要です", "warning");
      return;
    }

    const options = await collectCommitOptions(pi, ctx);
    if (!options) {
      notifyAndShutdown(ctx, "--commit をキャンセルしました", "info");
      return;
    }

    const previousActiveTools = pi.getActiveTools();
    let workflowToolsApplied = false;

    try {
      const snapshot = await gitSnapshot(pi);
      const selectedOptions = optionsForPrompt(options);
      const prompt = [
        `User invoked --commit with interactive options: ${selectedOptions}`,
        COMMIT_INSTRUCTIONS,
        HUMAN_RESPONSE_LANGUAGE_INSTRUCTION,
        "## Interactive Options",
        selectedOptions,
        "## Additional User Notes",
        options.additionalNotes
          ? `User-provided notes are inside this XML-like block.\n\n${formatAdditionalUserNotesBlock(options.additionalNotes)}`
          : "(none)",
        "## Initial Git Snapshot (may be stale; verify with live commands)",
        snapshot,
      ].join("\n\n");

      commitWorkflowActive = true;
      registerWorkflowTempFileTool(pi, "commit");
      applyWorkflowActiveTools(pi, "commit");
      workflowToolsApplied = true;
      pi.sendUserMessage(prompt);
    } catch (error) {
      commitWorkflowActive = false;
      if (workflowToolsApplied) pi.setActiveTools(previousActiveTools);
      const message = error instanceof Error ? error.message : String(error);
      notifyAndShutdown(
        ctx,
        `--commit の開始に失敗しました: ${message}`,
        "warning",
      );
    }
  };

  pi.on("session_start", async (event, ctx) => {
    if (
      event.reason !== "startup" ||
      startupCommitLaunched ||
      pi.getFlag("commit") !== true
    )
      return;
    startupCommitLaunched = true;
    await startCommitWorkflow(ctx);
  });

  pi.on("before_agent_start", async () => {
    if (!commitWorkflowActive) return;
    applyWorkflowActiveTools(pi, "commit");
  });

  pi.on("tool_call", async (event) => {
    if (!commitWorkflowActive) return undefined;
    return evaluateWorkflowToolCall("commit", event);
  });

  pi.on("agent_end", async (_event, ctx) => {
    if (!commitWorkflowActive) return;
    commitWorkflowActive = false;
    ctx.shutdown();
  });
}
