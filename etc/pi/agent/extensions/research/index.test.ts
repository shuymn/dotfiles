import { describe, expect, mock, test } from "bun:test";

import {
  createFakePi as createSharedFakePi,
  type ExecCall,
  type ExecResult,
} from "../test-support/fake-pi";
import { installTypeboxMock } from "../test-support/typebox-mock";

mock.module("@earendil-works/pi-ai", () => ({
  StringEnum: (values: readonly string[], options = {}) => ({
    enum: values,
    ...options,
  }),
}));
mock.module("@earendil-works/pi-coding-agent", () => ({}));
installTypeboxMock();

type ToolDefinition = {
  name: string;
  label: string;
  description: string;
  promptSnippet?: string;
  promptGuidelines?: string[];
  parameters: unknown;
  execute: (
    toolCallId: string,
    params: any,
    signal: AbortSignal | undefined,
    onUpdate:
      | ((update: { content: Array<{ type: "text"; text: string }> }) => void)
      | undefined,
    ctx?: any,
  ) => Promise<{
    content: Array<{ type: "text"; text: string }>;
    details: any;
  }>;
};

type CommandDefinition = {
  description?: string;
  handler: (args: string, ctx: FakeCommandContext) => Promise<void> | void;
};

type FakeCommandContext = {
  cwd: string;
  waitForIdle: () => Promise<void>;
  ui: {
    notify: (message: string, level: "info" | "warning" | "error") => void;
  };
};

function defaultExec(): ExecResult {
  return { code: 0, stdout: JSON.stringify({ ok: true }), stderr: "" };
}

function createFakePi(
  execHandler: (
    call: ExecCall,
  ) => ExecResult | Promise<ExecResult> = defaultExec,
) {
  return createSharedFakePi<ToolDefinition, CommandDefinition>({
    exec: execHandler,
  });
}

function createCommandContext() {
  const notifications: Array<{ message: string; level: string }> = [];
  return {
    ctx: {
      cwd: "/repo",
      async waitForIdle() {},
      ui: {
        notify(message: string, level: "info" | "warning" | "error") {
          notifications.push({ message, level });
        },
      },
    },
    notifications,
  };
}

async function loadExtension() {
  return (await import("./index")).default;
}

async function shutdown(pi: ReturnType<typeof createFakePi>) {
  for (const handler of pi.getEventHandlers("session_shutdown")) {
    await handler({}, { ui: { notify() {} } });
  }
}

describe("research extension", () => {
  test("registers /research command and deep_research tool", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect([...pi.commands.keys()]).toEqual(["research"]);
    expect(pi.commands.get("research")?.description).toContain("multi-stage");
    expect([...pi.tools.keys()].sort()).toEqual([
      "deep_research",
      "tavily_research",
    ]);
    expect(pi.tools.get("deep_research")!).toMatchObject({
      label: "Deep Research",
      parameters: {
        type: "object",
        properties: {
          task: { type: "string" },
          depth: { enum: ["quick", "standard", "deep"], optional: true },
          profile: {
            enum: ["general", "academic", "technical", "market", "news"],
            optional: true,
          },
          allowTavilyResearch: { type: "boolean", optional: true },
        },
      },
    });
    expect(
      pi.tools.get("deep_research")!.promptGuidelines!.join("\n"),
    ).toContain("queues a staged workflow");
  });

  test("/research queues the first Frame phase instead of injecting a one-shot prompt", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const { ctx, notifications } = createCommandContext();
    await pi.commands
      .get("research")!
      .handler(" React Server Components risks ", ctx);

    expect(pi.sentMessages).toHaveLength(1);
    expect(pi.sentMessages[0]!.message).toMatchObject({
      customType: "research-command",
      display: false,
      details: {
        phase: "01-frame.md",
        phaseIndex: 1,
        phaseCount: 4,
      },
    });
    expect(pi.sentMessages[0]!.message.content).toContain(
      "Run only phase 1/4: Frame",
    );
    expect(pi.sentMessages[0]!.message.content).toContain(
      "React Server Components risks",
    );
    expect(pi.sentMessages[0]!.options).toEqual({ triggerTurn: true });
    expect(notifications).toEqual([
      {
        message: "/research: phase 1/4 をキューに追加しました。",
        level: "info",
      },
    ]);

    await shutdown(pi);
  });

  test("/research validates empty task and active workflow with Japanese notifications", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const empty = createCommandContext();
    await pi.commands.get("research")!.handler("   ", empty.ctx);
    expect(empty.notifications).toEqual([
      {
        message:
          "調査タスクを指定してください。例: /research React Server Components adoption risks in 2026",
        level: "warning",
      },
    ]);

    const first = createCommandContext();
    await pi.commands.get("research")!.handler("task", first.ctx);
    const second = createCommandContext();
    await pi.commands.get("research")!.handler("another task", second.ctx);
    expect(second.notifications).toEqual([
      {
        message: "/research: 別のリサーチワークフローが既に実行中です。",
        level: "warning",
      },
    ]);

    await shutdown(pi);
  });

  test("/research cancel clears an active workflow", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const start = createCommandContext();
    await pi.commands.get("research")!.handler("task", start.ctx);

    const cancel = createCommandContext();
    await pi.commands.get("research")!.handler("cancel", cancel.ctx);

    expect(cancel.notifications).toEqual([
      {
        message: expect.stringContaining(
          "/research: ワークフロー ",
        ) as unknown as string,
        level: "info",
      },
    ]);

    const restart = createCommandContext();
    await pi.commands.get("research")!.handler("new task", restart.ctx);
    expect(restart.notifications).toEqual([
      {
        message: "/research: phase 1/4 をキューに追加しました。",
        level: "info",
      },
    ]);

    await shutdown(pi);
  });

  test("deep_research queues a staged workflow and returns run details", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const result = await pi.tools.get("deep_research")!.execute(
      "call",
      {
        task: "AI coding agent benchmarks",
        depth: "quick",
        profile: "academic",
        maxSources: 2,
      },
      undefined,
      undefined,
      { cwd: "/repo", hasUI: false },
    );

    expect(pi.execCalls).toEqual([]);
    expect(pi.sentMessages).toHaveLength(1);
    expect(pi.sentMessages[0]!.message.content).toContain(
      "Run only phase 1/4: Frame",
    );
    expect(result.content[0].text).toContain("Queued research workflow");
    expect(result.details).toMatchObject({
      status: "queued",
      phase: "01-frame.md",
      phaseIndex: 1,
      phaseCount: 4,
      options: {
        task: "AI coding agent benchmarks",
        depth: "quick",
        profile: "academic",
        maxSources: 2,
        allowTavilyResearch: false,
      },
    });

    await shutdown(pi);
  });

  test("tavily_research requires explicit approval and runs tvly research", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    await expect(
      pi.tools
        .get("tavily_research")!
        .execute(
          "call",
          { task: "deep task", approved: false },
          undefined,
          undefined,
        ),
    ).rejects.toThrow("requires explicit user approval");

    const result = await pi.tools.get("tavily_research")!.execute(
      "call",
      {
        task: "deep task",
        approved: true,
        model: "mini",
        citationFormat: "apa",
        timeoutSeconds: 30,
      },
      undefined,
      undefined,
    );

    expect(pi.execCalls).toEqual([
      {
        command: "tvly",
        args: [
          "research",
          "run",
          "deep task",
          "--json",
          "--model",
          "mini",
          "--citation-format",
          "apa",
          "--timeout",
          "30",
        ],
        options: { signal: undefined, timeout: 600_000 },
      },
    ]);
    expect(result.details.json).toEqual({ ok: true });
  });

  test("/research send failure clears active workflow", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    const originalSendMessage = pi.sendMessage;
    let fail = true;
    pi.sendMessage = ((message: any, options: unknown) => {
      if (fail) {
        fail = false;
        throw new Error("send failed");
      }
      originalSendMessage(message, options);
    }) as typeof pi.sendMessage;
    extension(pi as never);

    const failed = createCommandContext();
    await pi.commands.get("research")!.handler("task", failed.ctx);
    expect(failed.notifications).toEqual([
      {
        message:
          "/research: ワークフローの phase をキューに追加できませんでした。 send failed",
        level: "error",
      },
    ]);

    const retry = createCommandContext();
    await pi.commands.get("research")!.handler("retry", retry.ctx);
    expect(retry.notifications).toEqual([
      {
        message: "/research: phase 1/4 をキューに追加しました。",
        level: "info",
      },
    ]);

    await shutdown(pi);
  });

  test("next phase send failure clears active workflow", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const { ctx } = createCommandContext();
    await pi.commands.get("research")!.handler("task", ctx);
    const originalSendMessage = pi.sendMessage;
    pi.sendMessage = (() => {
      throw new Error("send failed");
    }) as typeof pi.sendMessage;

    await pi.getEventHandlers("agent_end")[0](
      {
        messages: [
          {
            role: "assistant",
            content: [{ type: "text", text: "frame notes" }],
          },
        ],
      },
      { ui: { notify() {} } },
    );
    await new Promise((resolve) => setTimeout(resolve, 0));

    pi.sendMessage = originalSendMessage;
    const retry = createCommandContext();
    await pi.commands.get("research")!.handler("retry", retry.ctx);
    expect(retry.notifications).toEqual([
      {
        message: "/research: phase 1/4 をキューに追加しました。",
        level: "info",
      },
    ]);

    await shutdown(pi);
  });

  test("agent_end advances the queued workflow to the next phase", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const { ctx } = createCommandContext();
    await pi.commands.get("research")!.handler("task", ctx);
    expect(pi.sentMessages).toHaveLength(1);

    await pi.getEventHandlers("agent_end")[0](
      {
        messages: [
          {
            role: "assistant",
            content: [{ type: "text", text: "frame notes" }],
          },
        ],
      },
      { ui: { notify() {} } },
    );
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(pi.sentMessages).toHaveLength(2);
    expect(pi.sentMessages[1]!.message).toMatchObject({
      customType: "research-command",
      details: {
        phase: "02-collect.md",
        phaseIndex: 2,
        phaseCount: 4,
      },
    });
    expect(pi.sentMessages[1]!.message.content).toContain(
      "Previous phase outputs",
    );
    expect(pi.sentMessages[1]!.message.content).toContain("frame notes");

    await shutdown(pi);
  });

  test("deep_research reports an already running workflow", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    await pi.tools
      .get("deep_research")!
      .execute("call", { task: "first" }, undefined, undefined, {
        cwd: "/repo",
        hasUI: false,
      });
    const result = await pi.tools
      .get("deep_research")!
      .execute("call", { task: "second" }, undefined, undefined, {
        cwd: "/repo",
        hasUI: false,
      });

    expect(result.content[0].text).toBe(
      "Another research workflow is already running.",
    );
    expect(result.details.activeRunId).toBeDefined();

    await shutdown(pi);
  });
});
