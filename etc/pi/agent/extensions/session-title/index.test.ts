import { describe, expect, mock, test } from "bun:test";

let completeImpl: (...args: unknown[]) => Promise<unknown> = async () => ({
  content: [{ type: "text", text: "Generated Title" }],
});

mock.module("@earendil-works/pi-ai", () => ({
  complete: (...args: unknown[]) => completeImpl(...args),
}));

type EventHandler = (event: any, ctx: any) => Promise<void> | void;

function createFakePi(flags: Record<string, unknown> = {}) {
  const events = new Map<string, EventHandler[]>();
  const flagValues = new Map(Object.entries(flags));
  const registeredFlags = new Set<string>();
  let sessionName: string | undefined;
  let resolveSetName: ((name: string) => void) | undefined;
  const setNamePromise = new Promise<string>((resolve) => {
    resolveSetName = resolve;
  });

  return {
    events,
    setNames: [] as string[],
    flags: [] as Array<{ name: string; definition: unknown }>,
    getFlagCalls: [] as string[],
    on(eventName: string, handler: EventHandler) {
      events.set(eventName, [...(events.get(eventName) ?? []), handler]);
    },
    registerFlag(name: string, definition: unknown) {
      registeredFlags.add(name);
      this.flags.push({ name, definition });
      if (
        definition &&
        typeof definition === "object" &&
        "default" in definition &&
        !flagValues.has(name)
      ) {
        flagValues.set(name, definition.default);
      }
    },
    getFlag(name: string) {
      this.getFlagCalls.push(name);
      if (!registeredFlags.has(name)) return undefined;
      return flagValues.get(name);
    },
    getSessionName() {
      return sessionName;
    },
    setSessionName(name: string) {
      sessionName = name;
      this.setNames.push(name);
      resolveSetName?.(name);
    },
    waitForSetName() {
      return setNamePromise;
    },
  };
}

function createCtx(
  entries: unknown[] = [],
  getApiKeyAndHeaders: () => Promise<unknown> = async () => ({
    ok: true,
    apiKey: "test-key",
    headers: { "x-test": "1" },
  }),
) {
  return {
    sessionManager: {
      getBranch: () => entries,
    },
    modelRegistry: {
      find: (provider: string, modelId: string) => ({ provider, id: modelId }),
      getApiKeyAndHeaders,
    },
  };
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

async function withTimeout<T>(
  promise: Promise<T>,
  message: string,
): Promise<T> {
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      promise,
      new Promise<never>((_, reject) => {
        timeout = setTimeout(() => reject(new Error(message)), 1_000);
      }),
    ]);
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}

async function loadExtension() {
  return await import("./index");
}

async function loadTitleHelpers() {
  return await import("./title");
}

describe("session-title extension", () => {
  test("arms only fresh unnamed startup or new sessions", async () => {
    const { shouldArmSessionTitle } = await loadTitleHelpers();

    expect(shouldArmSessionTitle("startup", [], undefined)).toBe(true);
    expect(shouldArmSessionTitle("new", [], undefined)).toBe(true);
    expect(shouldArmSessionTitle("resume", [], undefined)).toBe(false);
    expect(shouldArmSessionTitle("startup", [], "Named")).toBe(false);
    expect(
      shouldArmSessionTitle(
        "startup",
        [
          {
            type: "message",
            id: "entry-1",
            parentId: null,
            timestamp: "2026-01-01T00:00:00.000Z",
            message: { role: "user", content: "hello", timestamp: 1 },
          },
        ],
        undefined,
      ),
    ).toBe(false);
  });

  test("extracts and sanitizes generated titles", async () => {
    const { extractUserText, sanitizeSessionName } = await loadTitleHelpers();

    expect(
      extractUserText([
        { type: "text", text: "調査してください" },
        { type: "image", data: "ignored" },
        { type: "text", text: "pi extension" },
      ]),
    ).toBe("調査してください\npi extension");
    expect(sanitizeSessionName('Title: "Auto Name Session".')).toBe(
      "Auto Name Session",
    );
    expect(sanitizeSessionName('"Auto Name Session."')).toBe(
      "Auto Name Session",
    );
    expect(sanitizeSessionName("タイトル：『セッション自動命名』。 ")).toBe(
      "セッション自動命名",
    );
    expect(sanitizeSessionName("π - Implement Auto Naming")).toBe(
      "Implement Auto Naming",
    );
    expect(sanitizeSessionName("Title:\nImplement Auto Naming")).toBe(
      "Implement Auto Naming",
    );
  });

  test("registers and honors --no-session-title", async () => {
    const { default: extension } = await loadExtension();
    const pi = createFakePi({ "no-session-title": true });
    const ctx = createCtx();
    const completeCalls: unknown[][] = [];
    completeImpl = async (...args: unknown[]) => {
      completeCalls.push(args);
      return { content: [{ type: "text", text: "Should Not Run" }] };
    };

    extension(pi as never);

    expect(pi.flags).toEqual([
      {
        name: "no-session-title",
        definition: {
          description: "セッション名の自動生成を無効にする",
          type: "boolean",
          default: false,
        },
      },
    ]);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);
    await pi.events.get("message_end")![0](
      { message: { role: "user", content: "name this" } },
      ctx,
    );

    expect(completeCalls).toEqual([]);
    expect(pi.setNames).toEqual([]);
  });

  test("does not rely on unregistered one-shot workflow flags", async () => {
    const { default: extension } = await loadExtension();

    for (const flag of ["commit", "create-pr"] as const) {
      const pi = createFakePi({ [flag]: true });
      const ctx = createCtx();
      completeImpl = async () => ({
        content: [
          { type: "text", text: "Generated Despite Unregistered Flag" },
        ],
      });

      extension(pi as never);

      await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);
      await pi.events.get("message_end")![0](
        { message: { role: "user", content: "name this" } },
        ctx,
      );

      await expect(
        withTimeout(pi.waitForSetName(), "session name was not set"),
      ).resolves.toBe("Generated Despite Unregistered Flag");
      expect(pi.getFlagCalls).toEqual(["no-session-title"]);
    }
  });

  test("generates a title in the background without notifying or injecting context", async () => {
    const { default: extension } = await loadExtension();
    const pi = createFakePi();
    const ctx = createCtx();
    const completeCalls: unknown[][] = [];
    const completion = deferred<unknown>();
    completeImpl = async (...args: unknown[]) => {
      completeCalls.push(args);
      return completion.promise;
    };

    extension(pi as never);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);
    await pi.events.get("message_end")![0](
      { message: { role: "user", content: "pi session title please" } },
      ctx,
    );

    expect(pi.setNames).toEqual([]);
    completion.resolve({
      content: [
        {
          type: "toolCall",
          id: "call-1",
          name: "set_session_title",
          arguments: { title: "Implement Auto Naming" },
        },
      ],
    });

    await expect(
      withTimeout(pi.waitForSetName(), "session name was not set"),
    ).resolves.toBe("Implement Auto Naming");
    expect(pi.setNames).toEqual(["Implement Auto Naming"]);
    expect(completeCalls).toHaveLength(1);
    const options = completeCalls[0]![2] as Record<string, unknown>;
    expect(options).toMatchObject({
      reasoningEffort: "low",
      timeoutMs: 15_000,
    });
    expect(options).not.toHaveProperty("maxTokens");
    expect(options).not.toHaveProperty("maxRetries");
    const context = completeCalls[0]![1] as {
      tools?: Array<{ name: string }>;
    };
    expect(context.tools?.map((tool) => tool.name)).toEqual([
      "set_session_title",
    ]);
  });

  test("uses the first valid structured title", async () => {
    const { default: extension } = await loadExtension();
    const pi = createFakePi();
    const ctx = createCtx();
    completeImpl = async () => ({
      content: [
        {
          type: "toolCall",
          id: "call-1",
          name: "set_session_title",
          arguments: { title: 123 },
        },
        {
          type: "toolCall",
          id: "call-2",
          name: "set_session_title",
          arguments: {
            title:
              "Implement Automatic Session Naming for Pi Extension Workflow Tests",
          },
        },
      ],
    });

    extension(pi as never);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);
    await pi.events.get("message_end")![0](
      { message: { role: "user", content: "pi session title please" } },
      ctx,
    );

    await expect(
      withTimeout(pi.waitForSetName(), "session name was not set"),
    ).resolves.toBe("Implement Automatic Session Naming for Pi Extension");
  });

  test("falls back to text title when structured tool call is absent", async () => {
    const { default: extension } = await loadExtension();
    const pi = createFakePi();
    const ctx = createCtx();
    completeImpl = async () => ({
      content: [{ type: "text", text: "Implement Text Fallback" }],
    });

    extension(pi as never);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);
    await pi.events.get("message_end")![0](
      { message: { role: "user", content: "pi session title please" } },
      ctx,
    );

    await expect(
      withTimeout(pi.waitForSetName(), "session name was not set"),
    ).resolves.toBe("Implement Text Fallback");
  });

  test("does not start completion after auth resolves for an aborted session", async () => {
    const { default: extension } = await loadExtension();
    const pi = createFakePi();
    const auth = deferred<unknown>();
    const ctx = createCtx([], async () => auth.promise);
    const completeCalls: unknown[][] = [];
    completeImpl = async (...args: unknown[]) => {
      completeCalls.push(args);
      return { content: [{ type: "text", text: "Should Not Run" }] };
    };

    extension(pi as never);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);
    await pi.events.get("message_end")![0](
      { message: { role: "user", content: "name this" } },
      ctx,
    );
    await pi.events.get("session_shutdown")![0]({ reason: "quit" }, ctx);
    auth.resolve({ ok: true, apiKey: "test-key", headers: {} });
    await Promise.resolve();

    expect(completeCalls).toEqual([]);
    expect(pi.setNames).toEqual([]);
  });

  test("aborts in-flight generation on session shutdown", async () => {
    const { default: extension } = await loadExtension();
    const pi = createFakePi();
    const ctx = createCtx();
    let capturedSignal: AbortSignal | undefined;
    let resolveSignalCaptured: () => void = () => {};
    const signalCaptured = new Promise<void>((resolve) => {
      resolveSignalCaptured = resolve;
    });
    completeImpl = async (...args: unknown[]) => {
      capturedSignal = (args[2] as { signal?: AbortSignal }).signal;
      resolveSignalCaptured();
      return new Promise(() => {});
    };

    extension(pi as never);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);
    await pi.events.get("message_end")![0](
      { message: { role: "user", content: "name this" } },
      ctx,
    );
    await withTimeout(signalCaptured, "complete signal was not captured");

    await pi.events.get("session_shutdown")![0]({ reason: "quit" }, ctx);

    expect(capturedSignal?.aborted).toBe(true);
    expect(pi.setNames).toEqual([]);
  });

  test("silently ignores title generation failures", async () => {
    const { default: extension } = await loadExtension();
    const pi = createFakePi();
    const ctx = createCtx();
    const completion = deferred<unknown>();
    let completeSettled: () => void = () => {};
    const completeSettledPromise = new Promise<void>((resolve) => {
      completeSettled = resolve;
    });
    completeImpl = async () => {
      try {
        return await completion.promise;
      } finally {
        completeSettled();
      }
    };

    extension(pi as never);

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);
    await pi.events.get("message_end")![0](
      { message: { role: "user", content: "name this" } },
      ctx,
    );
    completion.reject(new Error("network down"));
    await withTimeout(completeSettledPromise, "complete did not settle");

    expect(pi.setNames).toEqual([]);
  });
});
