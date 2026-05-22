import { describe, expect, test } from "bun:test";
import { getWorkflowActiveTools } from "../lib/workflow-tool-policy";
import {
  type CustomAction,
  createCustomDriver,
  installTuiMocks,
} from "../test-support/tui-mocks";

const tuiInstances = installTuiMocks({
  codingAgent: {
    isToolCallEventType: (name: string, event: { toolName?: string }) =>
      event.toolName === name,
  },
});

const EXPECTED_WORKFLOW_TOOLS = getWorkflowActiveTools("commit");

type ExecCall = {
  command: string;
  args: string[];
  options: Record<string, unknown>;
};
type ExecResult = { code: number; stdout: string; stderr: string };
type EventHandler = (event: any, ctx?: any) => Promise<any> | any;

function defaultExec(call: ExecCall): ExecResult {
  if (call.command !== "git")
    return { code: 1, stdout: "", stderr: "unexpected" };
  const joined = call.args.join(" ");
  if (joined === "symbolic-ref --quiet --short refs/remotes/origin/HEAD")
    return { code: 0, stdout: "origin/main\n", stderr: "" };
  if (
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
  if (joined === "config --get user.email")
    return { code: 0, stdout: "dev@example.com\n", stderr: "" };
  if (joined === "status --short")
    return { code: 0, stdout: " M src/app.ts\n", stderr: "" };
  if (joined === "branch --show-current")
    return { code: 0, stdout: "feature\n", stderr: "" };
  if (joined === "log --author=dev@example\\.com --format=%s -10")
    return { code: 0, stdout: "feat: self commit\n", stderr: "" };
  if (joined === "log --format=%s -10")
    return { code: 0, stdout: "fix: all commit\n", stderr: "" };
  if (joined === "diff --stat")
    return { code: 0, stdout: "src/app.ts | 2 +-\n", stderr: "" };
  if (joined === "diff --cached --stat")
    return { code: 0, stdout: "", stderr: "" };
  return { code: 1, stdout: "", stderr: `unexpected git args: ${joined}` };
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

describe("commit extension", () => {
  test("registers --commit flag and lifecycle guards", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect(pi.registeredFlags).toEqual([
      {
        name: "commit",
        definition: {
          description: "対話式の commit ワークフローを実行して pi を終了する",
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

  test("does nothing unless startup session has --commit flag", async () => {
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
    busyPi.flags.set("commit", true);
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
    noUiPi.flags.set("commit", true);
    const noUiCtx = createContext([], { hasUI: false });

    await noUiPi.events.get("session_start")![0](
      { reason: "startup" },
      noUiCtx,
    );

    expect(noUiCtx.notifications).toEqual([
      { message: "--commit には対話式 UI が必要です", level: "warning" },
    ]);
    expect(noUiCtx.shutdownCount).toBe(1);
  });

  test("cancels cleanly when option collection is cancelled", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("commit", true);
    const ctx = createContext([{ kind: "select", value: null }]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(ctx.notifications).toEqual([
      { message: "--commit をキャンセルしました", level: "info" },
    ]);
    expect(ctx.shutdownCount).toBe(1);
    expect(pi.sentUserMessages).toEqual([]);
  });

  test("starts commit workflow with selected options and a git snapshot", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("commit", true);
    const ctx = createContext([
      { kind: "select", value: "japanese" },
      { kind: "select", value: "no" },
      { kind: "input", value: " package-lock.json は無視 " },
    ]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(ctx.notifications).toEqual([]);
    expect(ctx.shutdownCount).toBe(0);
    expect(pi.sentUserMessages).toHaveLength(1);
    const prompt = pi.sentUserMessages[0];
    expect(prompt).toContain(
      "User invoked --commit with interactive options: --japanese",
    );
    expect(prompt).toContain("## 人間向けレスポンスの言語");
    expect(prompt).toContain(
      "## Additional User Notes\n\nUser-provided notes are inside this XML-like block.\n\n<additional_user_notes>\npackage-lock.json は無視\n</additional_user_notes>",
    );
    expect(prompt).toContain("### Status\nM src/app.ts");
    expect(prompt).toContain(
      "### Recent Self Commits (primary for auto language)\nfeat: self commit",
    );
    expect(prompt).toContain("### Staged\n(empty)");
    expect(prompt).not.toContain("$(git config user.email)");
    expect(prompt).not.toContain("| wc -c");
    expect(pi.activeToolSets).toEqual([EXPECTED_WORKFLOW_TOOLS]);
    expect(pi.registeredTools.map((tool) => tool.name)).toEqual([
      "workflow_write_temp_file",
    ]);
    expect(pi.execCalls.map((call) => call.args.join(" "))).toEqual([
      "config --get user.email",
      "status --short",
      "branch --show-current",
      "log --author=dev@example\\.com --format=%s -10",
      "log --format=%s -10",
      "diff --stat",
      "diff --cached --stat",
    ]);
  });

  test("reapplies active tools before agent start while workflow is active", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("commit", true);
    const ctx = createContext([
      { kind: "select", value: "auto" },
      { kind: "select", value: "no" },
      { kind: "input", value: "" },
    ]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);
    await pi.events.get("before_agent_start")![0]({});

    expect(pi.activeToolSets).toEqual([
      EXPECTED_WORKFLOW_TOOLS,
      EXPECTED_WORKFLOW_TOOLS,
    ]);
  });

  test("branch creation flow discovers branches and includes base branch flag", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("commit", true);
    const ctx = createContext([
      { kind: "select", value: "english" },
      { kind: "select", value: "yes" },
      { kind: "select", value: "main" },
      { kind: "input", value: "" },
    ]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(pi.sentUserMessages[0]).toContain(
      "User invoked --commit with interactive options: --english --branch --base=main",
    );
    expect(pi.sentUserMessages[0]).toContain(
      "## Additional User Notes\n\n(none)",
    );
    expect(pi.execCalls.map((call) => call.args.join(" ")).slice(0, 3)).toEqual(
      [
        "symbolic-ref --quiet --short refs/remotes/origin/HEAD",
        "for-each-ref --format=%(refname)%09%(refname:short) refs/heads refs/remotes",
        "config --get user.email",
      ],
    );
  });

  test("blocks destructive git commands and push only while commit workflow is active", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const inactiveResult = await pi.events.get("tool_call")![0]({
      toolName: "bash",
      input: { command: "git reset --hard" },
    });
    expect(inactiveResult).toBeUndefined();

    pi.flags.set("commit", true);
    const ctx = createContext([
      { kind: "select", value: "auto" },
      { kind: "select", value: "no" },
      { kind: "input", value: "" },
    ]);
    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    const destructiveCommands = [
      "git restore .",
      "echo ok && git reset --hard",
      "git checkout -- src/app.ts",
      "git checkout -f main",
      "git switch feature --discard-changes",
      "git clean -fd",
    ];
    for (const command of destructiveCommands) {
      const result = await pi.events.get("tool_call")![0]({
        toolName: "bash",
        input: { command },
      });
      expect(result?.block).toBe(true);
      expect(result?.reason).toContain(
        "/commit extension によりブロックしました",
      );
      expect(result?.reason).toContain(
        "destructive git cleanup/reset commands",
      );
    }

    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "bash",
        input: { command: "git status --short" },
      }),
    ).resolves.toBeUndefined();
    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "read",
        input: { command: "git reset --hard" },
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
    ).resolves.toMatchObject({ block: true });
  });

  test("commit workflow blocks write tools and allows required commit commands", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("commit", true);
    const ctx = createContext([
      { kind: "select", value: "auto" },
      { kind: "select", value: "no" },
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
        toolName: "shell_command",
        input: { command: "git add commit/index.ts" },
      }),
    ).resolves.toBeUndefined();
    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "shell_command",
        input: { command: "git add -A" },
      }),
    ).resolves.toMatchObject({ block: true });
    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "bash",
        input: { command: "git commit -m 'test: update commit extension'" },
      }),
    ).resolves.toBeUndefined();
    for (const command of [
      "git commit --amend",
      "git commit --no-verify -m test",
      "git switch main",
      "git apply /tmp/change.patch",
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
        input: { command: "git switch -c fix/test main" },
      }),
    ).resolves.toBeUndefined();
    await expect(
      pi.events.get("tool_call")![0]({
        toolName: "shell_command",
        input: { command: "git apply --check --cached /tmp/change.patch" },
      }),
    ).resolves.toBeUndefined();

    const subagentEvent = { toolName: "spawn_subagent", input: {} };
    await expect(
      pi.events.get("tool_call")![0](subagentEvent),
    ).resolves.toBeUndefined();
    expect(subagentEvent.input).toEqual({ readOnly: true });
  });

  test("restores active tools if prompt delivery fails", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    pi.sendUserMessage = () => {
      throw new Error("send failed");
    };
    extension(pi as never);
    pi.flags.set("commit", true);
    const ctx = createContext([
      { kind: "select", value: "auto" },
      { kind: "select", value: "no" },
      { kind: "input", value: "" },
    ]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(ctx.notifications).toEqual([
      {
        message: "--commit の開始に失敗しました: send failed",
        level: "warning",
      },
    ]);
    expect(ctx.shutdownCount).toBe(1);
    expect(pi.activeToolSets).toEqual([
      EXPECTED_WORKFLOW_TOOLS,
      ["read", "bash", "edit", "write", "todo"],
    ]);
  });

  test("agent_end shuts down once after an active workflow", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("commit", true);
    const ctx = createContext([
      { kind: "select", value: "auto" },
      { kind: "select", value: "no" },
      { kind: "input", value: "" },
    ]);
    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    await pi.events.get("agent_end")![0]({}, ctx);
    await pi.events.get("agent_end")![0]({}, ctx);

    expect(ctx.shutdownCount).toBe(1);
  });
});
