import { describe, expect, test } from "bun:test";
import { getWorkflowActiveTools } from "../lib/workflow-tool-policy";
import {
  type CustomAction,
  createCustomDriver,
  installTuiMocks,
} from "../test-support/tui-mocks";

const tuiInstances = installTuiMocks();

const EXPECTED_WORKFLOW_TOOLS = getWorkflowActiveTools("create-pr");

type ExecCall = {
  command: string;
  args: string[];
  options: Record<string, unknown>;
};
type ExecResult = { code: number; stdout: string; stderr: string };
type EventHandler = (event: any, ctx?: any) => Promise<any> | any;

function defaultExec(call: ExecCall): ExecResult {
  const joined = call.args.join(" ");
  if (
    call.command === "git" &&
    joined === "symbolic-ref --quiet --short refs/remotes/origin/HEAD"
  ) {
    return { code: 0, stdout: "origin/main\n", stderr: "" };
  }
  if (
    call.command === "git" &&
    joined ===
      "for-each-ref --format=%(refname)%09%(refname:short) refs/heads refs/remotes"
  ) {
    return {
      code: 0,
      stdout:
        "refs/heads/feature\tfeature\nrefs/heads/main\tmain\nrefs/remotes/origin/main\torigin/main\nrefs/remotes/origin/HEAD\torigin/HEAD\n",
      stderr: "",
    };
  }
  if (call.command === "git" && joined === "branch --show-current")
    return { code: 0, stdout: "feature\n", stderr: "" };
  if (call.command === "git" && joined === "branch -r")
    return { code: 0, stdout: "  origin/main\n  origin/feature\n", stderr: "" };
  if (call.command === "git" && joined === "rev-parse --show-toplevel")
    return { code: 0, stdout: "/repo\n", stderr: "" };
  if (call.command === "git" && joined === "status -sb")
    return {
      code: 0,
      stdout: "## feature...origin/feature [ahead 2]\n",
      stderr: "",
    };
  if (call.command === "git" && joined === "log origin/main..HEAD --oneline")
    return { code: 0, stdout: "abc123 feat: add api\n", stderr: "" };
  if (
    call.command === "git" &&
    joined === "diff --name-status origin/main..HEAD"
  )
    return { code: 0, stdout: "M\tsrc/app.ts\n", stderr: "" };
  if (call.command === "git" && joined === "log --oneline -10")
    return {
      code: 0,
      stdout: "abc123 feat: add api\ndef456 fix: bug\n",
      stderr: "",
    };
  if (call.command === "git" && joined === "show --stat --oneline -5")
    return {
      code: 0,
      stdout: "abc123 feat: add api\n src/app.ts | 2 ++\n",
      stderr: "",
    };
  if (
    call.command === "bash" &&
    joined.startsWith("-lc cat .github/pull_request_template.md")
  ) {
    return { code: 0, stdout: "## Summary\n\n## Test plan\n", stderr: "" };
  }
  return {
    code: 1,
    stdout: "",
    stderr: `unexpected command: ${call.command} ${joined}`,
  };
}

function createFakePi(
  execHandler: (
    call: ExecCall,
  ) => ExecResult | Promise<ExecResult> = defaultExec,
) {
  const flags = new Map<string, unknown>();
  const events = new Map<string, EventHandler[]>();
  const registeredFlags: Array<{ name: string; definition: unknown }> = [];
  const execCalls: ExecCall[] = [];
  const sentUserMessages: string[] = [];
  const activeToolSets: string[][] = [];
  let activeTools = ["read", "bash", "edit", "write", "todo"];
  const registeredTools: Array<{ name: string; [key: string]: unknown }> = [];

  return {
    flags,
    events,
    registeredFlags,
    execCalls,
    sentUserMessages,
    registerFlag(name: string, definition: unknown) {
      registeredFlags.push({ name, definition });
    },
    registerTool(definition: { name: string; [key: string]: unknown }) {
      registeredTools.push(definition);
    },
    on(eventName: string, handler: EventHandler) {
      events.set(eventName, [...(events.get(eventName) ?? []), handler]);
    },
    getFlag(name: string) {
      return flags.get(name);
    },
    async exec(
      command: string,
      args: string[],
      options: Record<string, unknown> = {},
    ) {
      const call = { command, args, options };
      execCalls.push(call);
      return execHandler(call);
    },
    sendUserMessage(message: string) {
      sentUserMessages.push(message);
    },
    getActiveTools() {
      return [...activeTools];
    },
    setActiveTools(tools: string[]) {
      activeTools = [...tools];
      activeToolSets.push([...tools]);
    },
    activeToolSets,
    registeredTools,
  };
}

function createContext(
  actions: CustomAction[],
  options: { idle?: boolean; hasUI?: boolean } = {},
) {
  const notifications: Array<{ message: string; level: string }> = [];
  let shutdownCount = 0;

  return {
    notifications,
    get shutdownCount() {
      return shutdownCount;
    },
    hasUI: options.hasUI ?? true,
    isIdle: () => options.idle ?? true,
    shutdown: () => {
      shutdownCount += 1;
    },
    ui: {
      notify(message: string, level: string) {
        notifications.push({ message, level });
      },
      custom: createCustomDriver(actions, tuiInstances),
    },
  };
}

async function loadExtension() {
  return (await import("./index")).default;
}

describe("create-pr extension", () => {
  test("registers --create-pr flag and lifecycle hooks", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect(pi.registeredFlags).toEqual([
      {
        name: "create-pr",
        definition: {
          description:
            "対話式の create-pr ワークフローを実行して pi を終了する",
          type: "boolean",
          default: false,
        },
      },
    ]);
    expect([...pi.events.keys()].sort()).toEqual([
      "agent_end",
      "before_agent_start",
      "session_start",
      "tool_call",
    ]);
    expect(pi.registeredTools).toEqual([]);
  });

  test("does nothing unless startup session has --create-pr flag", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext([]);

    await pi.events.get("session_start")![0]({ reason: "resume" }, ctx);
    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(ctx.notifications).toEqual([]);
    expect(ctx.shutdownCount).toBe(0);
    expect(pi.sentUserMessages).toEqual([]);
    expect(pi.execCalls).toEqual([]);
  });

  test("shuts down with Japanese warning when the workflow cannot start", async () => {
    const extension = await loadExtension();
    const busyPi = createFakePi();
    extension(busyPi as never);
    busyPi.flags.set("create-pr", true);
    const busyCtx = createContext([], { idle: false });

    await busyPi.events.get("session_start")![0](
      { reason: "startup" },
      busyCtx,
    );

    expect(busyCtx.notifications).toEqual([
      {
        message: "エージェントが処理中です。処理を終了します。",
        level: "warning",
      },
    ]);
    expect(busyCtx.shutdownCount).toBe(1);

    const noUiPi = createFakePi();
    extension(noUiPi as never);
    noUiPi.flags.set("create-pr", true);
    const noUiCtx = createContext([], { hasUI: false });

    await noUiPi.events.get("session_start")![0](
      { reason: "startup" },
      noUiCtx,
    );

    expect(noUiCtx.notifications).toEqual([
      { message: "--create-pr には対話式 UI が必要です", level: "warning" },
    ]);
    expect(noUiCtx.shutdownCount).toBe(1);
  });

  test("cancels cleanly when option collection is cancelled", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("create-pr", true);
    const ctx = createContext([{ kind: "select", value: null }]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(ctx.notifications).toEqual([
      { message: "--create-pr をキャンセルしました", level: "info" },
    ]);
    expect(ctx.shutdownCount).toBe(1);
    expect(pi.sentUserMessages).toEqual([]);
  });

  test("create mode discovers base branch and sends a PR creation prompt with snapshot", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("create-pr", true);
    const ctx = createContext([
      { kind: "select", value: "japanese" },
      { kind: "select", value: "create" },
      { kind: "select", value: "main" },
      { kind: "input", value: " README は無視 " },
    ]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(ctx.notifications).toEqual([]);
    expect(ctx.shutdownCount).toBe(0);
    expect(pi.sentUserMessages).toHaveLength(1);
    const prompt = pi.sentUserMessages[0];
    expect(prompt).toContain(
      "User invoked --create-pr with interactive options: --japanese --base=main",
    );
    expect(prompt).toContain("## 人間向けレスポンスの言語");
    expect(prompt).toContain(
      "## Additional User Notes\n\nUser-provided notes are inside this XML-like block.\n\n<additional_user_notes>\nREADME は無視\n</additional_user_notes>",
    );
    expect(prompt).toContain(
      "## Initial Git/GitHub Snapshot (may be stale; verify with live commands)",
    );
    expect(prompt).toContain("### Current branch\nfeature");
    expect(prompt).toContain("### Default branch\nmain");
    expect(prompt).toContain("### Committed changes\nabc123 feat: add api");
    expect(prompt).toContain("### Files changed\nM\tsrc/app.ts");
    expect(prompt).toContain("### PR template\n## Summary");
    expect(prompt).not.toContain("2>/dev/null");
    expect(prompt).not.toContain("| sed");
    expect(prompt).not.toContain("<<'EOF'");
    expect(pi.activeToolSets).toEqual([EXPECTED_WORKFLOW_TOOLS]);
    expect(pi.registeredTools.map((tool) => tool.name)).toEqual([
      "workflow_write_temp_file",
    ]);
    expect(
      pi.execCalls.map((call) => [call.command, call.args.join(" ")]),
    ).toEqual([
      ["git", "symbolic-ref --quiet --short refs/remotes/origin/HEAD"],
      [
        "git",
        "for-each-ref --format=%(refname)%09%(refname:short) refs/heads refs/remotes",
      ],
      [
        "bash",
        "-lc cat .github/pull_request_template.md 2>/dev/null || cat .github/PULL_REQUEST_TEMPLATE.md 2>/dev/null || echo 'No GitHub template'",
      ],
      ["git", "branch --show-current"],
      ["git", "branch -r"],
      ["git", "symbolic-ref --quiet --short refs/remotes/origin/HEAD"],
      ["git", "rev-parse --show-toplevel"],
      ["git", "status -sb"],
      ["git", "log origin/main..HEAD --oneline"],
      ["git", "diff --name-status origin/main..HEAD"],
    ]);
  });

  test("reapplies active tools before agent start while workflow is active", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("create-pr", true);
    const ctx = createContext([
      { kind: "select", value: "english" },
      { kind: "select", value: "update" },
      { kind: "input", value: "" },
    ]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);
    await pi.events.get("before_agent_start")![0]({});

    expect(pi.activeToolSets).toEqual([
      EXPECTED_WORKFLOW_TOOLS,
      EXPECTED_WORKFLOW_TOOLS,
    ]);
  });

  test("create-pr workflow gates tools and shell commands", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "shell_command",
        input: { command: "git push origin HEAD" },
      }),
    ).resolves.toBeUndefined();

    pi.flags.set("create-pr", true);
    const ctx = createContext([
      { kind: "select", value: "english" },
      { kind: "select", value: "update" },
      { kind: "input", value: "" },
    ]);
    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    for (const toolName of ["apply_patch", "edit", "write"]) {
      await expect(
        pi.events.get("tool_call")![0]({ toolName, input: {} }),
      ).resolves.toMatchObject({ block: true });
    }

    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "bash",
        input: { command: "git status --short" },
      }),
    ).resolves.toBeUndefined();
    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "shell_command",
        input: { command: "git reset --hard" },
      }),
    ).resolves.toMatchObject({ block: true });
    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "bash",
        input: { command: "git push origin HEAD" },
      }),
    ).resolves.toBeUndefined();
    for (const command of [
      "git push --force origin HEAD",
      "git push --delete origin main",
      "git push --tags",
      "git push origin :main",
      "git push origin +HEAD",
    ]) {
      await expect(
        pi.events.get("tool_call")![0]({
          toolName: "shell_command",
          input: { command },
        }),
      ).resolves.toMatchObject({ block: true });
    }
    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "shell_command",
        input: {
          command: "gh pr create --title test --body-file /tmp/body.md",
        },
      }),
    ).resolves.toBeUndefined();
    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "shell_command",
        input: { command: "gh pr create --fill" },
      }),
    ).resolves.toMatchObject({ block: true });
    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "shell_command",
        input: {
          command: "gh pr edit 1 --title test --body-file /tmp/body.md",
        },
      }),
    ).resolves.toBeUndefined();

    const subagentEvent = { toolName: "spawn_subagent", input: {} };
    await expect(
      pi.events.get("tool_call")![0](subagentEvent),
    ).resolves.toBeUndefined();
    expect(subagentEvent.input).toEqual({ readOnly: true });
  });

  test("update mode skips base branch selection and snapshots existing PR context", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("create-pr", true);
    const ctx = createContext([
      { kind: "select", value: "english" },
      { kind: "select", value: "update" },
      { kind: "input", value: "" },
    ]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    const prompt = pi.sentUserMessages[0];
    expect(prompt).toContain(
      "User invoked --create-pr with interactive options: --update",
    );
    expect(prompt).toContain("## Additional User Notes\n\n(none)");
    expect(prompt).toContain(
      "### Committed changes\nabc123 feat: add api\ndef456 fix: bug",
    );
    expect(prompt).toContain(
      "### Files changed\nabc123 feat: add api\n src/app.ts | 2 ++",
    );
    expect(pi.execCalls.map((call) => call.args.join(" "))).not.toContain(
      "for-each-ref --format=%(refname)%09%(refname:short) refs/heads refs/remotes",
    );
    expect(pi.execCalls.map((call) => call.args.join(" "))).toContain(
      "log --oneline -10",
    );
    expect(pi.execCalls.map((call) => call.args.join(" "))).toContain(
      "show --stat --oneline -5",
    );
  });

  test("falls back to main when no branches are discoverable for create mode", async () => {
    const extension = await loadExtension();
    const pi = createFakePi((call) => {
      const joined = call.args.join(" ");
      if (
        call.command === "git" &&
        joined === "symbolic-ref --quiet --short refs/remotes/origin/HEAD"
      )
        return { code: 1, stdout: "", stderr: "" };
      if (
        call.command === "git" &&
        joined === "show-ref --verify --quiet refs/heads/main"
      )
        return { code: 1, stdout: "", stderr: "" };
      if (
        call.command === "git" &&
        joined === "show-ref --verify --quiet refs/heads/master"
      )
        return { code: 1, stdout: "", stderr: "" };
      if (
        call.command === "git" &&
        joined ===
          "for-each-ref --format=%(refname)%09%(refname:short) refs/heads refs/remotes"
      )
        return { code: 0, stdout: "", stderr: "" };
      return defaultExec(call);
    });
    extension(pi as never);
    pi.flags.set("create-pr", true);
    const ctx = createContext([
      { kind: "select", value: "english" },
      { kind: "select", value: "create" },
      { kind: "select", value: "main" },
      { kind: "input", value: "" },
    ]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(pi.sentUserMessages[0]).toContain(
      "User invoked --create-pr with interactive options: --base=main",
    );
    expect(pi.execCalls.map((call) => call.args.join(" ")).slice(0, 4)).toEqual(
      [
        "symbolic-ref --quiet --short refs/remotes/origin/HEAD",
        "show-ref --verify --quiet refs/heads/main",
        "show-ref --verify --quiet refs/heads/master",
        "for-each-ref --format=%(refname)%09%(refname:short) refs/heads refs/remotes",
      ],
    );
  });

  test("notifies and shuts down if prompt delivery fails", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    pi.sendUserMessage = () => {
      throw new Error("send failed");
    };
    extension(pi as never);
    pi.flags.set("create-pr", true);
    const ctx = createContext([
      { kind: "select", value: "english" },
      { kind: "select", value: "update" },
      { kind: "input", value: "" },
    ]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(ctx.notifications).toEqual([
      {
        message: "--create-pr の開始に失敗しました: send failed",
        level: "warning",
      },
    ]);
    expect(ctx.shutdownCount).toBe(1);
    expect(pi.sentUserMessages).toEqual([]);
    expect(pi.activeToolSets).toEqual([
      EXPECTED_WORKFLOW_TOOLS,
      ["read", "bash", "edit", "write", "todo"],
    ]);
  });

  test("agent_end shuts down once after an active workflow", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("create-pr", true);
    const ctx = createContext([
      { kind: "select", value: "english" },
      { kind: "select", value: "update" },
      { kind: "input", value: "" },
    ]);
    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    await pi.events.get("agent_end")![0]({}, ctx);
    await pi.events.get("agent_end")![0]({}, ctx);

    expect(ctx.shutdownCount).toBe(1);
  });
});
