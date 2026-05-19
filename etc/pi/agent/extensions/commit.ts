import { readFileSync } from "node:fs";
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import {
  getSelectListTheme,
  isToolCallEventType,
} from "@earendil-works/pi-coding-agent";
import {
  fuzzyFilter,
  Key,
  matchesKey,
  SelectList,
  truncateToWidth,
  type SelectItem,
} from "@earendil-works/pi-tui";

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
};

const PROHIBITED_GIT_PATTERNS = [
  /(^|[;&|]\s*)git\s+restore\b/,
  /(^|[;&|]\s*)git\s+reset\b/,
  /(^|[;&|]\s*)git\s+checkout\s+(?:--|-f\b)/,
  /(^|[;&|]\s*)git\s+switch\b[^\n;|&]*\s--discard-changes\b/,
  /(^|[;&|]\s*)git\s+clean\b/,
];

function isPrintableInput(data: string): boolean {
  return (
    data.length > 0 &&
    !data.startsWith("\x1b") &&
    !data.startsWith("\x7f") &&
    !data.startsWith("\r")
  );
}

async function selectFuzzy(
  ctx: ExtensionContext,
  title: string,
  items: SelectItem[],
  initialValue?: string,
): Promise<string | null> {
  return await ctx.ui.custom<string | null>(
    (tui, theme, _keybindings, done) => {
      let query = "";
      let filteredItems = items;
      let list: SelectList;

      const makeList = () => {
        filteredItems = query.trim()
          ? fuzzyFilter(
              items,
              query.trim(),
              (item) => `${item.label} ${item.value} ${item.description ?? ""}`,
            )
          : items;
        list = new SelectList(
          filteredItems,
          Math.min(Math.max(filteredItems.length, 1), 12),
          getSelectListTheme(),
        );
        const initialIndex = filteredItems.findIndex(
          (item) => item.value === initialValue,
        );
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
            theme.fg("dim", `検索: ${query || "(入力して絞り込み)"}`),
            ...list.render(width),
            truncateToWidth(
              theme.fg(
                "dim",
                "入力で検索 • ↑↓で移動 • enterで選択 • escでキャンセル",
              ),
              width,
              "",
            ),
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
    },
  );
}

async function getDefaultBranch(pi: ExtensionAPI): Promise<string | undefined> {
  const symbolic = await pi
    .exec(
      "git",
      ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
      { timeout: 3000 },
    )
    .catch(() => undefined);
  if (symbolic?.code === 0)
    return symbolic.stdout.trim().replace(/^origin\//, "") || undefined;

  for (const candidate of ["main", "master"]) {
    const exists = await pi
      .exec(
        "git",
        ["show-ref", "--verify", "--quiet", `refs/heads/${candidate}`],
        { timeout: 3000 },
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

async function collectCommitOptions(
  pi: ExtensionAPI,
  ctx: ExtensionContext,
): Promise<CommitOptions | null> {
  const language = (await selectFuzzy(
    ctx,
    "コミットメッセージの言語",
    [
      {
        value: "auto",
        label: "自動",
        description: "直近のコミット履歴に合わせる。不明なら確認する",
      },
      { value: "english", label: "英語", description: "--english 相当" },
      { value: "japanese", label: "日本語", description: "--japanese 相当" },
    ],
    "auto",
  )) as CommitLanguage | null;
  if (!language) return null;

  const branchMode = await selectFuzzy(
    ctx,
    "先に新しいブランチを作成しますか？",
    [
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
    "no",
  );
  if (!branchMode) return null;

  if (branchMode === "no") return { language, createBranch: false };

  const defaultBranch = await getDefaultBranch(pi);
  const branches = await getBranches(pi, defaultBranch);
  const baseBranch = await selectFuzzy(
    ctx,
    "新しいブランチのベースブランチ",
    branches.length > 0
      ? branches
      : [
          {
            value: defaultBranch ?? "main",
            label: defaultBranch ?? "main",
            description: "フォールバック",
          },
        ],
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
    description: "対話式の /commit ワークフローを開いて pi を開始する",
    type: "boolean",
    default: false,
  });

  const startCommitWorkflow = async (
    ctx: ExtensionContext,
    notes: string,
    source: "command" | "flag",
  ) => {
    if (!ctx.isIdle()) {
      ctx.ui.notify(
        "エージェントが処理中です。現在のターンが完了してから /commit を再実行してください。",
        "warning",
      );
      return;
    }

    if (!ctx.hasUI) {
      ctx.ui.notify("/commit には対話式 UI が必要です", "warning");
      return;
    }

    const options = await collectCommitOptions(pi, ctx);
    if (!options) {
      ctx.ui.notify("/commit をキャンセルしました", "info");
      return;
    }

    commitWorkflowActive = true;
    const snapshot = await gitSnapshot(pi);
    const selectedOptions = optionsForPrompt(options);
    pi.sendUserMessage(
      `User invoked /commit via ${source} with interactive options: ${selectedOptions}\n\n${COMMIT_INSTRUCTIONS}\n\n${HUMAN_RESPONSE_LANGUAGE_INSTRUCTION}\n\n## Interactive Options\n\n${selectedOptions}\n\n## Additional User Notes\n\n${
        notes.trim() || "(none)"
      }\n\n## Initial Git Snapshot (may be stale; verify with live commands)\n\n${snapshot}`,
    );
  };

  pi.on("session_start", async (event, ctx) => {
    if (
      event.reason !== "startup" ||
      startupCommitLaunched ||
      pi.getFlag("commit") !== true
    )
      return;
    startupCommitLaunched = true;
    await startCommitWorkflow(ctx, "", "flag");
  });

  pi.registerCommand("commit", {
    description: "意味のある単位でローカル git コミットを対話的に作成する。",
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
          "/commit extension によりブロックしました: コミット準備中の破壊的な git cleanup/reset コマンドは禁止されています。代わりにユーザーへ明示的な指示を確認してください。",
      };
    }

    if (/(^|[;&|]\s*)git\s+push\b/.test(command)) {
      return {
        block: true,
        reason:
          "/commit extension によりブロックしました: /commit はローカルコミットのみを作成します。push しないでください。",
      };
    }

    return undefined;
  });

  pi.on("agent_end", async () => {
    commitWorkflowActive = false;
  });
}
