import { readFileSync } from "node:fs";
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { getSelectListTheme } from "@earendil-works/pi-coding-agent";
import {
  fuzzyFilter,
  Key,
  matchesKey,
  SelectList,
  truncateToWidth,
  type SelectItem,
} from "@earendil-works/pi-tui";

const CREATE_PR_INSTRUCTIONS = readFileSync(
  new URL("./create-pr-instructions.md", import.meta.url),
  "utf8",
);

type PrLanguage = "english" | "japanese";
type PrMode = "create" | "update";

type CreatePrOptions = {
  language: PrLanguage;
  mode: PrMode;
  baseBranch?: string;
};

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

async function collectCreatePrOptions(
  pi: ExtensionAPI,
  ctx: ExtensionContext,
): Promise<CreatePrOptions | null> {
  const language = (await selectFuzzy(
    ctx,
    "Pull request の言語",
    [
      { value: "english", label: "英語", description: "デフォルト" },
      {
        value: "japanese",
        label: "日本語",
        description: "PR タイトル/本文を日本語で作成する",
      },
    ],
    "english",
  )) as PrLanguage | null;
  if (!language) return null;

  const mode = (await selectFuzzy(
    ctx,
    "Pull request を作成または更新しますか？",
    [
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
    "create",
  )) as PrMode | null;
  if (!mode) return null;

  if (mode === "update") return { language, mode };

  const defaultBranch = await getDefaultBranch(pi);
  const branches = await getBranches(pi, defaultBranch);
  const baseBranch = await selectFuzzy(
    ctx,
    "Pull request のベースブランチ",
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

  return { language, mode, baseBranch };
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
  const commands: Array<[label: string, command: string]> = [
    ["Current branch", "git branch --show-current"],
    ["Remote branches", "git branch -r"],
    [
      "Default branch",
      "git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@' || true",
    ],
    ["Repository root", "git rev-parse --show-toplevel"],
    ["Push status", "git status -sb | head -1"],
    [
      "Committed changes",
      options.mode === "create"
        ? `git log origin/${base}..HEAD --oneline`
        : "git log --oneline -10",
    ],
    [
      "Files changed",
      options.mode === "create"
        ? `git diff --name-status origin/${base}..HEAD`
        : "git show --stat --oneline -5",
    ],
    [
      "PR template",
      "cat .github/pull_request_template.md 2>/dev/null || cat .github/PULL_REQUEST_TEMPLATE.md 2>/dev/null || echo 'No GitHub template'",
    ],
  ];

  const results = await Promise.all(
    commands.map(async ([label, command]) => {
      const result = await pi
        .exec("bash", ["-lc", command], { timeout: 5000 })
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
  let startupCreatePrLaunched = false;

  pi.registerFlag("create-pr", {
    description: "対話式の /create-pr ワークフローを開いて pi を開始する",
    type: "boolean",
    default: false,
  });

  const startCreatePrWorkflow = async (
    ctx: ExtensionContext,
    notes: string,
    source: "command" | "flag",
  ) => {
    if (!ctx.isIdle()) {
      ctx.ui.notify(
        "エージェントが処理中です。現在のターンが完了してから /create-pr を再実行してください。",
        "warning",
      );
      return;
    }

    if (!ctx.hasUI) {
      ctx.ui.notify("/create-pr には対話式 UI が必要です", "warning");
      return;
    }

    const options = await collectCreatePrOptions(pi, ctx);
    if (!options) {
      ctx.ui.notify("/create-pr をキャンセルしました", "info");
      return;
    }

    const snapshot = await gitSnapshot(pi, options);
    const selectedOptions = optionsForPrompt(options);
    pi.sendUserMessage(
      `User invoked /create-pr via ${source} with interactive options: ${selectedOptions}\n\n${CREATE_PR_INSTRUCTIONS}\n\n## 人間向けレスポンスの言語\n\nユーザーへの返答・確認・エラー説明など、人間に見せるメッセージは日本語で書くこと。これは選択された PR タイトル/本文の言語を変更しない。\n\n## Interactive Options\n\n${selectedOptions}\n\n## Additional User Notes\n\n${
        notes.trim() || "(none)"
      }\n\n## Initial Git/GitHub Snapshot (may be stale; verify with live commands)\n\n${snapshot}`,
    );
  };

  pi.on("session_start", async (event, ctx) => {
    if (
      event.reason !== "startup" ||
      startupCreatePrLaunched ||
      pi.getFlag("create-pr") !== true
    )
      return;
    startupCreatePrLaunched = true;
    await startCreatePrWorkflow(ctx, "", "flag");
  });

  pi.registerCommand("create-pr", {
    description:
      "コミット済みの変更から GitHub pull request を対話的に作成または更新する。",
    handler: async (args, ctx) => {
      await startCreatePrWorkflow(ctx, args, "command");
    },
  });
}
