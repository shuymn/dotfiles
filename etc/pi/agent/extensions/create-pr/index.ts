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

const CREATE_PR_INSTRUCTIONS = readFileSync(
  new URL("./create-pr-instructions.md", import.meta.url),
  "utf8",
);
const HUMAN_RESPONSE_LANGUAGE_INSTRUCTION = `## 人間向けレスポンスの言語

ユーザーへの返答・確認・エラー説明など、人間に見せるメッセージは日本語で書くこと。これは選択された PR タイトル/本文の言語を変更しない。`;

type PrLanguage = "english" | "japanese";
type PrMode = "create" | "update";

type CreatePrOptions = {
  language: PrLanguage;
  mode: PrMode;
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
    placeholder: "例: README の変更は無視してください。空 Enter でなし",
  });
}

async function collectCreatePrOptions(
  pi: ExtensionAPI,
  ctx: ExtensionContext,
): Promise<CreatePrOptions | null> {
  let step: "language" | "mode" | "baseBranch" | "additionalNotes" = "language";
  let language: PrLanguage = "english";
  let mode: PrMode = "create";
  let baseBranch: string | undefined;
  let defaultBranch: string | undefined;
  let branches: SelectItem[] | undefined;

  while (true) {
    if (step === "language") {
      const selectedLanguage = (await selectFuzzy(ctx, {
        title: "Pull request の言語",
        items: [
          { value: "english", label: "英語", description: "デフォルト" },
          {
            value: "japanese",
            label: "日本語",
            description: "PR タイトル/本文を日本語で作成する",
          },
        ],
        initialValue: language,
      })) as PrLanguage | null;
      if (!selectedLanguage) return null;
      language = selectedLanguage;
      step = "mode";
      continue;
    }

    if (step === "mode") {
      const selectedMode = (await selectFuzzy(ctx, {
        title: "Pull request を作成または更新しますか？",
        items: [
          {
            value: "create",
            label: "作成",
            description: "新しい pull request を作成する",
          },
          {
            value: "update",
            label: "更新",
            description: "現在のブランチの open PR を更新する",
          },
        ],
        initialValue: mode,
      })) as PrMode | null;
      if (!selectedMode) {
        step = "language";
        continue;
      }
      mode = selectedMode;
      step = mode === "create" ? "baseBranch" : "additionalNotes";
      continue;
    }

    if (step === "baseBranch") {
      if (!branches) {
        defaultBranch = await getDefaultBranch(pi);
        branches = await getBranches(pi, defaultBranch);
      }
      const selectedBaseBranch = await selectFuzzy(ctx, {
        title: "Pull request のベースブランチ",
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
        step = "mode";
        continue;
      }
      baseBranch = selectedBaseBranch;
      step = "additionalNotes";
      continue;
    }

    const additionalNotes = await collectAdditionalNotes(ctx);
    if (additionalNotes === null) {
      step = mode === "create" ? "baseBranch" : "mode";
      continue;
    }

    return mode === "create"
      ? { language, mode, baseBranch, additionalNotes }
      : { language, mode, additionalNotes };
  }
}

function optionsForPrompt(options: CreatePrOptions): string {
  const flags: string[] = [];
  if (options.language === "japanese") flags.push("--japanese");
  if (options.mode === "update") flags.push("--update");
  if (options.mode === "create" && options.baseBranch)
    flags.push(`--base=${options.baseBranch}`);
  return flags.join(" ") || "(none)";
}

async function gitSnapshot(
  pi: ExtensionAPI,
  options: CreatePrOptions,
): Promise<string> {
  const base = options.baseBranch ?? "<existing PR base>";
  const baseRange = `origin/${base}..HEAD`;
  const commands: Array<[label: string, args: string[]]> = [
    ["Current branch", ["branch", "--show-current"]],
    ["Remote branches", ["branch", "-r"]],
    [
      "Default branch",
      ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
    ],
    ["Repository root", ["rev-parse", "--show-toplevel"]],
    ["Push status", ["status", "-sb"]],
    [
      "Committed changes",
      options.mode === "create"
        ? ["log", baseRange, "--oneline"]
        : ["log", "--oneline", "-10"],
    ],
    [
      "Files changed",
      options.mode === "create"
        ? ["diff", "--name-status", baseRange]
        : ["show", "--stat", "--oneline", "-5"],
    ],
  ];

  const templateCommand =
    "cat .github/pull_request_template.md 2>/dev/null || " +
    "cat .github/PULL_REQUEST_TEMPLATE.md 2>/dev/null || " +
    "echo 'No GitHub template'";
  const templatePromise = pi
    .exec("bash", ["-lc", templateCommand], { timeout: 5000 })
    .catch((error: unknown) => ({
      code: 1,
      stdout: "",
      stderr: error instanceof Error ? error.message : String(error),
    }));

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
      const normalizedOutput =
        label === "Default branch"
          ? output.replace(/^origin\//, "") || "No default branch"
          : output;
      return `### ${label}\n${normalizedOutput || "(empty)"}`;
    }),
  );

  const template = await templatePromise;
  const templateOutput =
    `${template.stdout}${template.stderr ? `\n${template.stderr}` : ""}`.trim();
  results.push(`### PR template\n${templateOutput || "(empty)"}`);

  return results.join("\n\n");
}

export default function (pi: ExtensionAPI) {
  let createPrWorkflowActive = false;
  let startupCreatePrLaunched = false;

  pi.registerFlag("create-pr", {
    description: "対話式の create-pr ワークフローを実行して pi を終了する",
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

  const startCreatePrWorkflow = async (ctx: ExtensionContext) => {
    if (!ctx.isIdle()) {
      notifyAndShutdown(
        ctx,
        "エージェントが処理中です。処理を終了します。",
        "warning",
      );
      return;
    }

    if (!ctx.hasUI) {
      notifyAndShutdown(ctx, "--create-pr には対話式 UI が必要です", "warning");
      return;
    }

    const options = await collectCreatePrOptions(pi, ctx);
    if (!options) {
      notifyAndShutdown(ctx, "--create-pr をキャンセルしました", "info");
      return;
    }

    const previousActiveTools = pi.getActiveTools();
    let workflowToolsApplied = false;

    try {
      const snapshot = await gitSnapshot(pi, options);
      const selectedOptions = optionsForPrompt(options);
      const prompt = [
        `User invoked --create-pr with interactive options: ${selectedOptions}`,
        CREATE_PR_INSTRUCTIONS,
        HUMAN_RESPONSE_LANGUAGE_INSTRUCTION,
        "## Interactive Options",
        selectedOptions,
        "## Additional User Notes",
        options.additionalNotes
          ? `User-provided notes are inside this XML-like block.\n\n${formatAdditionalUserNotesBlock(options.additionalNotes)}`
          : "(none)",
        "## Initial Git/GitHub Snapshot (may be stale; verify with live commands)",
        snapshot,
      ].join("\n\n");

      createPrWorkflowActive = true;
      registerWorkflowTempFileTool(pi, "create-pr");
      applyWorkflowActiveTools(pi, "create-pr");
      workflowToolsApplied = true;
      pi.sendUserMessage(prompt);
    } catch (error) {
      createPrWorkflowActive = false;
      if (workflowToolsApplied) pi.setActiveTools(previousActiveTools);
      const message = error instanceof Error ? error.message : String(error);
      notifyAndShutdown(
        ctx,
        `--create-pr の開始に失敗しました: ${message}`,
        "warning",
      );
    }
  };

  pi.on("session_start", async (event, ctx) => {
    if (
      event.reason !== "startup" ||
      startupCreatePrLaunched ||
      pi.getFlag("create-pr") !== true
    )
      return;
    startupCreatePrLaunched = true;
    await startCreatePrWorkflow(ctx);
  });

  pi.on("before_agent_start", async () => {
    if (!createPrWorkflowActive) return;
    applyWorkflowActiveTools(pi, "create-pr");
  });

  pi.on("tool_call", async (event) => {
    if (!createPrWorkflowActive) return undefined;
    return evaluateWorkflowToolCall("create-pr", event);
  });

  pi.on("agent_end", async (_event, ctx) => {
    if (!createPrWorkflowActive) return;
    createPrWorkflowActive = false;
    ctx.shutdown();
  });
}
