import { afterEach, describe, expect, mock, test } from "bun:test";
import { mkdtemp, mkdir, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";

mock.module("typebox", () => {
  const Type = {
    Object: (properties: Record<string, unknown>, options = {}) => ({ type: "object", properties, ...options }),
    String: (options = {}) => ({ type: "string", ...options }),
    Boolean: (options = {}) => ({ type: "boolean", ...options }),
    Array: (items: unknown, options = {}) => ({ type: "array", items, ...options }),
    Optional: (schema: Record<string, unknown>) => ({ ...schema, optional: true }),
  };
  return { Type };
});

type ExecCall = { command: string; args: string[]; options: Record<string, unknown> };
type ExecResult = { code: number; stdout: string; stderr: string };
type EventHandler = (event: any, ctx: any) => Promise<any> | any;
type CommandHandler = (args: string, ctx: FakeCommandContext) => Promise<void> | void;
type ToolDefinition = {
  name: string;
  label: string;
  description: string;
  promptGuidelines: string[];
  parameters: unknown;
  execute: (
    toolCallId: string,
    params: { files?: string[]; staged?: boolean; noFix?: boolean },
    signal: AbortSignal | undefined,
    onUpdate: unknown,
    ctx: FakeRunContext,
  ) => Promise<{ content: Array<{ type: "text"; text: string }>; details: any }>;
};
type FakeRunContext = { cwd: string; ui: FakeUi };
type FakeCommandContext = FakeRunContext & { waitForIdle: () => Promise<void> };
type FakeUi = {
  notifications: Array<{ message: string; level: string }>;
  widgets: Array<{ key: string; lines: string[] | undefined; options?: unknown }>;
  notify: (message: string, level: string) => void;
  setWidget: (key: string, lines: string[] | undefined, options?: unknown) => void;
};

const tempDirs: string[] = [];
const createdPis: ReturnType<typeof createFakePi>[] = [];

function defaultExec(call: ExecCall): ExecResult {
  const args = call.args.join(" ");
  if (call.command === "git" && args === "diff --name-status -z") {
    return { code: 0, stdout: "M\0src/app.ts\0R100\0old.ts\0new.ts\0", stderr: "" };
  }
  if (call.command === "git" && args === "diff --cached --name-status -z") {
    return { code: 0, stdout: "A\0src/staged.ts\0", stderr: "" };
  }
  if (call.command === "git" && args === "ls-files --others --exclude-standard -z") {
    return { code: 0, stdout: "notes.txt\0", stderr: "" };
  }
  if (call.command === "git" && args.startsWith("diff HEAD --")) {
    return { code: 0, stdout: "diff --git a/src/app.ts b/src/app.ts\n+changed\n", stderr: "" };
  }
  if (call.command === "git" && args.startsWith("diff --cached --")) {
    return { code: 0, stdout: "diff --git a/src/staged.ts b/src/staged.ts\n+staged\n", stderr: "" };
  }
  return { code: 1, stdout: "", stderr: `unexpected git ${args}` };
}

function createFakePi(execHandler: (call: ExecCall) => ExecResult | Promise<ExecResult> = defaultExec) {
  const tools = new Map<string, ToolDefinition>();
  const commands = new Map<string, { description: string; handler: CommandHandler }>();
  const events = new Map<string, EventHandler[]>();
  const execCalls: ExecCall[] = [];
  const sentMessages: Array<{ message: any; options: unknown }> = [];

  const pi = {
    tools,
    commands,
    events,
    execCalls,
    sentMessages,
    registerTool(definition: ToolDefinition) { tools.set(definition.name, definition); },
    registerCommand(name: string, definition: { description: string; handler: CommandHandler }) { commands.set(name, definition); },
    on(eventName: string, handler: EventHandler) { events.set(eventName, [...(events.get(eventName) ?? []), handler]); },
    async exec(command: string, args: string[], options: Record<string, unknown>) {
      if (command === "git") {
        expect(options).toMatchObject({ cwd: expect.any(String), timeout: 10_000 });
      }
      const call = { command, args, options };
      execCalls.push(call);
      return execHandler(call);
    },
    sendMessage(message: any, options: unknown) { sentMessages.push({ message, options }); },
  };
  createdPis.push(pi);
  return pi;
}

function createUi(): FakeUi {
  const notifications: Array<{ message: string; level: string }> = [];
  const widgets: Array<{ key: string; lines: string[] | undefined; options?: unknown }> = [];
  return {
    notifications,
    widgets,
    notify(message: string, level: string) { notifications.push({ message, level }); },
    setWidget(key: string, lines: string[] | undefined, options?: unknown) { widgets.push({ key, lines, options }); },
  };
}

function createRunContext(cwd = "/repo"): FakeRunContext {
  return { cwd, ui: createUi() };
}

function createCommandContext(cwd = "/repo"): FakeCommandContext & { waited: { value: boolean } } {
  const waited = { value: false };
  return { ...createRunContext(cwd), waited, async waitForIdle() { waited.value = true; } };
}

async function loadExtension() {
  return (await import("./index")).default;
}

async function createTempDir() {
  const dir = await mkdtemp(join(tmpdir(), "review-extension-test-"));
  tempDirs.push(dir);
  return dir;
}

async function shutdownAllRuns() {
  for (const pi of createdPis) {
    const handler = pi.events.get("session_shutdown")?.[0];
    if (handler) await handler({}, createRunContext());
  }
  createdPis.splice(0);
}

afterEach(async () => {
  await shutdownAllRuns();
  await Promise.all(tempDirs.splice(0).map((dir) => rm(dir, { recursive: true, force: true })));
});

describe("review extension", () => {
  test("registers command and tool with schema and guidance", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect([...pi.commands.keys()]).toEqual(["review"]);
    expect(pi.commands.get("review")!.description).toContain("multi-stage code review workflow");
    expect([...pi.events.keys()].sort()).toEqual(["agent_end", "session_shutdown", "tool_call"]);
    const tool = pi.tools.get("review")!;
    expect(tool.label).toBe("Review");
    expect(tool.promptGuidelines.join("\n")).toContain("Use noFix when the user asks to report findings without fixing");
    expect(tool.parameters).toMatchObject({
      type: "object",
      properties: {
        files: { type: "array", optional: true },
        staged: { type: "boolean", optional: true },
        noFix: { type: "boolean", optional: true },
      },
    });
  });

  test("tool explicit-file mode queues the first phase without inspecting git status", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createRunContext();

    const result = await pi.tools.get("review")!.execute("call", { files: ["@src/app.ts", "docs/readme.md"] }, undefined, undefined, ctx);

    expect(pi.execCalls).toEqual([]);
    expect(pi.sentMessages).toHaveLength(1);
    expect(pi.sentMessages[0].message).toMatchObject({
      customType: "review-command",
      display: false,
      details: { phase: "01-recon.md", phaseIndex: 1, phaseCount: 9 },
    });
    expect(pi.sentMessages[0].message.content).toContain("Explicit file mode: git diff is intentionally ignored");
    expect(pi.sentMessages[0].message.content).toContain('- "src/app.ts" (explicit)');
    expect(result.content[0].text).toContain("Queued review workflow");
    expect(result.details.targets).toEqual([
      { path: "src/app.ts", status: "explicit", source: "explicit" },
      { path: "docs/readme.md", status: "explicit", source: "explicit" },
    ]);
    expect(ctx.ui.widgets[0]).toMatchObject({ key: "review-workflow", lines: ["/review: phase 1/9 running"] });
  });

  test("tool collects unstaged, staged, renamed, and untracked targets with diff context", async () => {
    const extension = await loadExtension();
    const cwd = await createTempDir();
    await writeFile(join(cwd, "notes.txt"), "untracked notes");
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createRunContext(cwd);

    const result = await pi.tools.get("review")!.execute("call", {}, undefined, undefined, ctx);

    expect(result.details.targets).toEqual([
      { path: "src/app.ts", status: "M", source: "diff" },
      { path: "new.ts", oldPath: "old.ts", status: "R100", source: "diff" },
      { path: "src/staged.ts", status: "A", source: "diff" },
      { path: "notes.txt", status: "untracked", source: "diff" },
    ]);
    const prompt = pi.sentMessages[0].message.content;
    expect(prompt).toContain('"old.ts" -> "new.ts" (R100; diff)');
    expect(prompt).toContain("## Combined diff against HEAD");
    expect(prompt).toContain('## Untracked file: "notes.txt"');
    expect(prompt).toContain("untracked notes");
  });

  test("staged mode reviews only cached changes and reports no-target cases", async () => {
    const extension = await loadExtension();
    const pi = createFakePi((call) => {
      if (call.command === "git" && call.args.join(" ") === "diff --cached --name-status -z") return { code: 0, stdout: "A\0staged.ts\0", stderr: "" };
      if (call.command === "git" && call.args.join(" ").startsWith("diff --cached --")) return { code: 0, stdout: "+cached", stderr: "" };
      return { code: 0, stdout: "", stderr: "" };
    });
    extension(pi as never);

    await pi.tools.get("review")!.execute("call", { staged: true }, undefined, undefined, createRunContext());

    expect(pi.execCalls.map((call) => call.args.join(" "))).toEqual([
      "diff --cached --name-status -z",
      "diff --cached -- staged.ts",
    ]);
    await shutdownAllRuns();

    const emptyPi = createFakePi(() => ({ code: 0, stdout: "", stderr: "" }));
    extension(emptyPi as never);
    const result = await emptyPi.tools.get("review")!.execute("call", {}, undefined, undefined, createRunContext());

    expect(result).toEqual({
      content: [{ type: "text", text: "No changed files found for review. Pass explicit files to review whole files." }],
      details: { targets: [] },
    });
    expect(emptyPi.sentMessages).toEqual([]);
  });

  test("read-only phases block mutating tools and force subagents to read-only", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    await pi.tools.get("review")!.execute("call", { files: ["src/app.ts"] }, undefined, undefined, createRunContext());

    await expect(pi.events.get("tool_call")![0]({ toolName: "read", input: {} })).resolves.toBeUndefined();
    const subagentEvent = { toolName: "spawn_subagent", input: { prompt: "inspect" } };
    await expect(pi.events.get("tool_call")![0](subagentEvent)).resolves.toBeUndefined();
    expect(subagentEvent.input).toEqual({ prompt: "inspect", readOnly: true });
    await expect(pi.events.get("tool_call")![0]({ toolName: "bash", input: { command: "echo hi" } })).resolves.toEqual({
      block: true,
      reason: "/review investigation phases are read-only. This tool is allowed only in Stage 7: Fix.",
    });
  });

  test("agent_end stores phase notes, advances phases, and completes workflow", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createRunContext();
    await pi.tools.get("review")!.execute("call", { files: ["src/app.ts"] }, undefined, undefined, ctx);

    await pi.events.get("agent_end")![0]({ messages: [{ role: "assistant", content: [{ type: "text", text: "recon notes" }] }] }, ctx);
    await new Promise((resolve) => setTimeout(resolve, 5));

    expect(pi.sentMessages).toHaveLength(2);
    expect(pi.sentMessages[1].message.details.phase).toBe("02-hunt.md");
    expect(pi.sentMessages[1].message.content).toContain("Completed phase 1: 01-recon.md");
    expect(pi.sentMessages[1].message.content).toContain("recon notes");
    expect(ctx.ui.widgets.at(-2)).toMatchObject({ lines: ["/review: phase 2/9 queued"] });
    expect(ctx.ui.widgets.at(-1)).toMatchObject({ lines: ["/review: phase 2/9 running"] });

    for (let index = 2; index <= 9; index += 1) {
      await pi.events.get("agent_end")![0]({ messages: [{ role: "assistant", content: `phase ${index} done` }] }, ctx);
      await new Promise((resolve) => setTimeout(resolve, 5));
    }

    expect(ctx.ui.notifications.at(-1)!.message).toMatch(/^\/review: workflow \d+ completed\.$/);
    expect(ctx.ui.widgets.at(-1)).toEqual({ key: "review-workflow", lines: undefined, options: undefined });
  });

  test("gapfill control can loop back to hunt but is capped", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createRunContext();
    await pi.tools.get("review")!.execute("call", { files: ["src/app.ts"] }, undefined, undefined, ctx);

    // Finish Recon, Hunt, Validate, then Gapfill with new tasks.
    for (const text of ["recon", "hunt", "validate"]) {
      await pi.events.get("agent_end")![0]({ messages: [{ role: "assistant", content: text }] }, ctx);
      await new Promise((resolve) => setTimeout(resolve, 5));
    }
    await pi.events.get("agent_end")![0]({ messages: [{ role: "assistant", content: '<review_control>{"new_hunt_tasks":[{"question":"q"}]}</review_control>' }] }, ctx);
    await new Promise((resolve) => setTimeout(resolve, 5));

    expect(pi.sentMessages.at(-1)!.message.details.phase).toBe("02-hunt.md");

    // Second gapfill loop is still allowed; third one advances to Dedupe.
    for (const expected of ["02-hunt.md", "05-dedupe.md"]) {
      await pi.events.get("agent_end")![0]({ messages: [{ role: "assistant", content: "hunt again" }] }, ctx);
      await new Promise((resolve) => setTimeout(resolve, 5));
      await pi.events.get("agent_end")![0]({ messages: [{ role: "assistant", content: "validate again" }] }, ctx);
      await new Promise((resolve) => setTimeout(resolve, 5));
      await pi.events.get("agent_end")![0]({ messages: [{ role: "assistant", content: '<review_control>{"new_hunt_tasks":[{"question":"q"}]}</review_control>' }] }, ctx);
      await new Promise((resolve) => setTimeout(resolve, 5));
      expect(pi.sentMessages.at(-1)!.message.details.phase).toBe(expected);
    }
  });

  test("no-fix mode skips fix phases and keeps every phase read-only", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createRunContext();

    await pi.tools.get("review")!.execute("call", { files: ["src/app.ts"], noFix: true }, undefined, undefined, ctx);

    expect(pi.sentMessages[0].message.details.phaseCount).toBe(7);
    expect(pi.sentMessages[0].message.content).toContain("No-fix mode is enabled: do not edit files");
    await expect(pi.events.get("tool_call")![0]({ toolName: "bash", input: { command: "echo hi" } })).resolves.toEqual({
      block: true,
      reason: "/review --no-fix mode is read-only. This tool is not allowed while producing a report.",
    });

    for (let index = 1; index <= 6; index += 1) {
      await pi.events.get("agent_end")![0]({ messages: [{ role: "assistant", content: `phase ${index}` }] }, ctx);
      await new Promise((resolve) => setTimeout(resolve, 5));
    }

    expect(pi.sentMessages.at(-1)!.message.details.phase).toBe("09-summary.md");
    expect(pi.sentMessages.at(-1)!.message.content).toContain("No-fix mode: consolidate the validated findings into a Japanese report.");
  });

  test("command supports explicit args, busy guard, and cancellation", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createCommandContext();

    await pi.commands.get("review")!.handler("--no-fix @src/app.ts", ctx);

    expect(ctx.waited.value).toBe(true);
    expect(ctx.ui.notifications).toContainEqual({ message: "/review: queued phase 1/7 for 1 file(s).", level: "info" });

    const busyCtx = createCommandContext();
    await pi.commands.get("review")!.handler("src/other.ts", busyCtx);
    expect(busyCtx.ui.notifications).toEqual([{ message: "/review: another review workflow is already running.", level: "warning" }]);

    const cancelCtx = createCommandContext();
    await pi.commands.get("review")!.handler("cancel", cancelCtx);
    expect(cancelCtx.ui.notifications[0].message).toMatch(/^\/review: cancelled workflow \d+\.$/);
    expect(cancelCtx.ui.widgets.at(-1)).toEqual({ key: "review-workflow", lines: undefined, options: undefined });
  });
});
