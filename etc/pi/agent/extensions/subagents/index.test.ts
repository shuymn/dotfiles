import { afterEach, describe, expect, mock, test } from "bun:test";

let uuidCounter = 0;
mock.module("node:crypto", () => ({
  randomUUID: () => `id${String(++uuidCounter).padStart(6, "0")}-0000-4000-8000-000000000000`,
}));

mock.module("typebox", () => {
  const Type = {
    Object: (properties: Record<string, unknown>, options = {}) => ({ type: "object", properties, ...options }),
    String: (options = {}) => ({ type: "string", ...options }),
    Boolean: (options = {}) => ({ type: "boolean", ...options }),
    Optional: (schema: Record<string, unknown>) => ({ ...schema, optional: true }),
  };
  return { Type };
});

type Subscriber = (event: any) => void;
type SessionBehavior = {
  resultText?: string;
  promptError?: Error;
  blockPrompt?: boolean;
  initialMessages?: Array<{ role: string; content: unknown }>;
};
type CreatedSession = ReturnType<typeof createSession>;

type ToolDefinition = {
  name: string;
  label: string;
  description: string;
  parameters: unknown;
  execute: (
    toolCallId: string,
    params: any,
    signal: AbortSignal | undefined,
    onUpdate: ((result: { content: Array<{ type: "text"; text: string }>; details: Record<string, unknown> }) => void) | undefined,
    ctx: FakeContext,
  ) => Promise<{ content: Array<{ type: "text"; text: string }>; details: Record<string, unknown> }>;
};
type EventHandler = (event: unknown, ctx: FakeContext) => Promise<void> | void;
type FakeContext = ReturnType<typeof createContext>;

const createAgentSessionCalls: any[] = [];
const loaderInstances: any[] = [];
const createdSessions: CreatedSession[] = [];
const createdPis: ReturnType<typeof createFakePi>[] = [];
let nextBehaviors: SessionBehavior[] = [];

function createSession(behavior: SessionBehavior) {
  const subscribers: Subscriber[] = [];
  let name = "";
  let aborted = false;
  let disposed = false;
  let releasePrompt: (() => void) | undefined;
  const promptStarted = Promise.withResolvers<void>();

  const session = {
    messages: [...(behavior.initialMessages ?? [])],
    get name() { return name; },
    get aborted() { return aborted; },
    get disposed() { return disposed; },
    get promptStarted() { return promptStarted.promise; },
    releasePrompt() { releasePrompt?.(); },
    setSessionName(value: string) { name = value; },
    subscribe(subscriber: Subscriber) {
      subscribers.push(subscriber);
      return () => {
        const index = subscribers.indexOf(subscriber);
        if (index >= 0) subscribers.splice(index, 1);
      };
    },
    async prompt(prompt: string) {
      (session as any).lastPrompt = prompt;
      promptStarted.resolve();
      subscribers.forEach((subscriber) => subscriber({ type: "message_start" }));
      for (const chunk of (behavior.resultText ?? "subagent result").match(/.{1,600}/gs) ?? []) {
        subscribers.forEach((subscriber) => subscriber({ type: "message_update", assistantMessageEvent: { type: "text_delta", delta: chunk } }));
      }
      if (behavior.blockPrompt) {
        await new Promise<void>((resolve) => { releasePrompt = resolve; });
      }
      if (behavior.promptError) throw behavior.promptError;
      session.messages.push({ role: "assistant", content: [{ type: "text", text: behavior.resultText ?? "subagent result" }] });
    },
    async abort() {
      aborted = true;
      releasePrompt?.();
    },
    dispose() {
      disposed = true;
    },
  };
  createdSessions.push(session);
  return session;
}

mock.module("@earendil-works/pi-coding-agent", () => ({
  getAgentDir: () => "/agent-dir",
  DefaultResourceLoader: class {
    options: unknown;
    reloaded = false;
    constructor(options: unknown) {
      this.options = options;
      loaderInstances.push(this);
    }
    async reload() { this.reloaded = true; }
  },
  SessionManager: {
    inMemory: (cwd: string) => ({ kind: "in-memory", cwd }),
  },
  SettingsManager: {
    create: (cwd: string, agentDir: string) => ({ cwd, agentDir }),
  },
  createAgentSession: async (options: unknown) => {
    createAgentSessionCalls.push(options);
    return { session: createSession(nextBehaviors.shift() ?? {}) };
  },
}));

function createFakePi() {
  const tools = new Map<string, ToolDefinition>();
  const events = new Map<string, EventHandler[]>();
  let thinkingLevel = "medium";

  const pi = {
    tools,
    events,
    setThinkingLevel(value: string) { thinkingLevel = value; },
    registerTool(definition: ToolDefinition) { tools.set(definition.name, definition); },
    on(eventName: string, handler: EventHandler) { events.set(eventName, [...(events.get(eventName) ?? []), handler]); },
    getThinkingLevel: () => thinkingLevel,
  };
  createdPis.push(pi);
  return pi;
}

function createContext() {
  return {
    cwd: "/repo",
    modelRegistry: { id: "registry" },
    model: { name: "model" },
    getSystemPrompt: () => "parent system prompt",
  };
}

async function loadExtension() {
  return (await import("./index")).default;
}

async function waitForCreatedSession(index = 0): Promise<CreatedSession> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (createdSessions[index]) return createdSessions[index];
    await Promise.resolve();
  }
  throw new Error(`session ${index} was not created`);
}

async function cleanupRecords() {
  for (const session of createdSessions) session.releasePrompt();
  for (const pi of createdPis) {
    const handler = pi.events.get("session_shutdown")?.[0];
    if (handler) await handler({}, createContext());
  }
  createdPis.splice(0);
}

afterEach(async () => {
  await cleanupRecords();
  uuidCounter = 0;
  nextBehaviors = [];
  createAgentSessionCalls.splice(0);
  loaderInstances.splice(0);
  createdSessions.splice(0);
});

describe("subagents extension", () => {
  test("registers four subagent tools and shutdown cleanup hook", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect([...pi.tools.keys()].sort()).toEqual(["get_subagent_result", "list_subagents", "spawn_subagent", "stop_subagent"]);
    expect([...pi.events.keys()]).toEqual(["session_shutdown"]);
    expect(pi.tools.get("spawn_subagent")!.parameters).toMatchObject({
      type: "object",
      properties: { prompt: { type: "string" }, background: { type: "boolean", optional: true }, readOnly: { type: "boolean", optional: true } },
    });
  });

  test("foreground spawn runs an isolated subagent session and returns streamed result", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    pi.setThinkingLevel("high");
    extension(pi as never);
    nextBehaviors = [{ resultText: "final answer" }];
    const updates: string[] = [];

    const result = await pi.tools.get("spawn_subagent")!.execute(
      "call",
      { prompt: "Investigate this", description: "Investigation" },
      undefined,
      (update) => updates.push(update.content[0].text),
      createContext(),
    );

    expect(result).toEqual({ content: [{ type: "text", text: "final answer" }], details: { id: "id000001", status: "completed" } });
    expect(updates).toEqual(["Subagent id000001 running...\n\nfinal answer"]);
    expect(createdSessions[0].name).toBe("subagent#id000001");
    expect(createdSessions[0].disposed).toBe(true);
    expect(createAgentSessionCalls[0]).toMatchObject({
      cwd: "/repo",
      agentDir: "/agent-dir",
      thinkingLevel: "high",
      tools: ["read", "write", "edit", "bash"],
      model: { name: "model" },
      modelRegistry: { id: "registry" },
    });
    expect(loaderInstances[0].reloaded).toBe(true);
    expect(loaderInstances[0].options.systemPromptOverride()).toContain("parent system prompt");
    expect(loaderInstances[0].options.systemPromptOverride()).toContain("Working directory: /repo");
  });

  test("readOnly spawn restricts tools and adds read-only system prompt rule", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    nextBehaviors = [{ resultText: "read only result" }];

    await pi.tools.get("spawn_subagent")!.execute("call", { prompt: "Inspect", readOnly: true }, undefined, undefined, createContext());

    expect(createAgentSessionCalls[0].tools).toEqual(["read"]);
    expect(loaderInstances[0].options.systemPromptOverride()).toContain("This subagent is read-only: do not edit files or run mutating shell commands.");
  });

  test("foreground spawn reports errors and removes completed records", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    nextBehaviors = [{ promptError: new Error("boom") }];

    const result = await pi.tools.get("spawn_subagent")!.execute("call", { prompt: "Fail" }, undefined, undefined, createContext());

    expect(result).toEqual({ content: [{ type: "text", text: "Subagent error: boom" }], details: { id: "id000001", status: "error" } });
    expect(createdSessions[0].disposed).toBe(true);
    const list = await pi.tools.get("list_subagents")!.execute("call", {}, undefined, undefined, createContext());
    expect(list).toEqual({ content: [{ type: "text", text: "No subagents in this session." }], details: { count: 0 } });
  });

  test("foreground parent abort stops the subagent", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    nextBehaviors = [{ resultText: "partial", blockPrompt: true }];
    const abortController = new AbortController();

    const promise = pi.tools.get("spawn_subagent")!.execute("call", { prompt: "Long" }, abortController.signal, undefined, createContext());
    const session = await waitForCreatedSession();
    await session.promptStarted;
    abortController.abort();
    const result = await promise;

    expect(session.aborted).toBe(true);
    expect(result.details).toEqual({ id: "id000001", status: "stopped" });
    expect(result.content[0].text).toBe("Subagent stopped: stopped");
  });

  test("background spawn can be listed and retrieved after completion", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    nextBehaviors = [{ resultText: "background answer" }];

    const started = await pi.tools.get("spawn_subagent")!.execute(
      "call",
      { prompt: "Work", description: "Background job", background: true },
      undefined,
      undefined,
      createContext(),
    );

    expect(started).toEqual({
      content: [{ type: "text", text: "Subagent started in background.\nID: id000001\nDescription: Background job\n\nUse get_subagent_result with this ID to check status or retrieve the full result." }],
      details: { id: "id000001", status: "running", background: true },
    });
    expect((await pi.tools.get("list_subagents")!.execute("call", {}, undefined, undefined, createContext())).content[0].text).toContain("id000001 | running");

    const result = await pi.tools.get("get_subagent_result")!.execute("call", { id: "id000001", wait: true }, undefined, undefined, createContext());

    expect(result.content[0].text).toContain("Subagent id000001 | completed |");
    expect(result.content[0].text).toContain("Description: Background job");
    expect(result.content[0].text).toContain("background answer");
    expect(result.details).toEqual({});
  });

  test("get_subagent_result handles missing and still-running subagents", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    expect(await pi.tools.get("get_subagent_result")!.execute("call", { id: "missing" }, undefined, undefined, createContext())).toEqual({
      content: [{ type: "text", text: "Subagent not found: missing" }],
      details: {},
    });

    nextBehaviors = [{ resultText: "eventual", blockPrompt: true }];
    await pi.tools.get("spawn_subagent")!.execute("call", { prompt: "Long", background: true }, undefined, undefined, createContext());
    await createdSessions[0].promptStarted;

    const running = await pi.tools.get("get_subagent_result")!.execute("call", { id: "id000001" }, undefined, undefined, createContext());
    expect(running.content[0].text).toContain("Subagent id000001 | running |");
    expect(running.content[0].text).toContain("Still running.");
    createdSessions[0].releasePrompt();
    await pi.tools.get("get_subagent_result")!.execute("call", { id: "id000001", wait: true }, undefined, undefined, createContext());
  });

  test("stop_subagent aborts a running background subagent and reports non-running records", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    nextBehaviors = [{ resultText: "partial", blockPrompt: true }];
    await pi.tools.get("spawn_subagent")!.execute("call", { prompt: "Long", background: true }, undefined, undefined, createContext());
    await createdSessions[0].promptStarted;

    const stopped = await pi.tools.get("stop_subagent")!.execute("call", { id: "id000001" }, undefined, undefined, createContext());

    expect(createdSessions[0].aborted).toBe(true);
    expect(stopped).toEqual({ content: [{ type: "text", text: "Stopped subagent id000001." }], details: { id: "id000001", status: "stopped" } });
    const secondStop = await pi.tools.get("stop_subagent")!.execute("call", { id: "id000001" }, undefined, undefined, createContext());
    expect(secondStop.content[0].text).toBe("Subagent id000001 is not running (status: stopped).");
    expect(await pi.tools.get("stop_subagent")!.execute("call", { id: "missing" }, undefined, undefined, createContext())).toEqual({
      content: [{ type: "text", text: "Subagent not found: missing" }],
      details: {},
    });
  });

  test("session shutdown aborts active subagents, disposes sessions, and clears records", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    nextBehaviors = [{ resultText: "partial", blockPrompt: true }];
    await pi.tools.get("spawn_subagent")!.execute("call", { prompt: "Long", background: true }, undefined, undefined, createContext());
    await createdSessions[0].promptStarted;

    await pi.events.get("session_shutdown")![0]({}, createContext());

    expect(createdSessions[0].aborted).toBe(true);
    expect(createdSessions[0].disposed).toBe(true);
    expect(await pi.tools.get("list_subagents")!.execute("call", {}, undefined, undefined, createContext())).toEqual({
      content: [{ type: "text", text: "No subagents in this session." }],
      details: { count: 0 },
    });
  });

  test("foreground update text is truncated", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    nextBehaviors = [{ resultText: "x".repeat(1300) }];
    const updates: string[] = [];

    await pi.tools.get("spawn_subagent")!.execute("call", { prompt: "Long output" }, undefined, (update) => updates.push(update.content[0].text), createContext());

    expect(updates.at(-1)).toContain("...(truncated; call get_subagent_result for full output)");
  });
});
