import { afterEach, describe, expect, mock, test } from "bun:test";

const writes: Array<{ fd: number; text: string }> = [];
let throwOnWrite = false;

mock.module("node:fs", () => ({
  writeSync: (fd: number, text: string) => {
    if (throwOnWrite) throw new Error("stdout closed");
    writes.push({ fd, text });
    return text.length;
  },
}));

type EventHandler = (event: any, ctx: any) => Promise<any> | any;
type CommandHandler = (args: string, ctx: { shutdown: () => void }) => Promise<void> | void;

type ProcessPatch = {
  exitListeners: Array<(...args: unknown[]) => void>;
  offCalls: Array<{ event: string; listener: (...args: unknown[]) => void }>;
  restore: () => void;
};

let currentPatch: ProcessPatch | undefined;

function patchProcessExitHooks(): ProcessPatch {
  const originalOnce = process.once;
  const originalOff = process.off;
  const exitListeners: Array<(...args: unknown[]) => void> = [];
  const offCalls: Array<{ event: string; listener: (...args: unknown[]) => void }> = [];

  process.once = ((event: string | symbol, listener: (...args: unknown[]) => void) => {
    if (event === "exit") {
      exitListeners.push(listener);
      return process;
    }
    return originalOnce.call(process, event, listener as never);
  }) as typeof process.once;

  process.off = ((event: string | symbol, listener: (...args: unknown[]) => void) => {
    if (event === "exit") {
      offCalls.push({ event, listener });
      return process;
    }
    return originalOff.call(process, event, listener as never);
  }) as typeof process.off;

  currentPatch = {
    exitListeners,
    offCalls,
    restore: () => {
      process.once = originalOnce;
      process.off = originalOff;
      currentPatch = undefined;
    },
  };
  return currentPatch;
}

function createFakePi() {
  const commands = new Map<string, { description: string; handler: CommandHandler }>();
  const events = new Map<string, EventHandler[]>();

  return {
    commands,
    events,
    registerCommand(name: string, definition: { description: string; handler: CommandHandler }) {
      commands.set(name, definition);
    },
    on(eventName: string, handler: EventHandler) {
      events.set(eventName, [...(events.get(eventName) ?? []), handler]);
    },
  };
}

async function loadExtension() {
  return (await import("./index")).default;
}

afterEach(() => {
  currentPatch?.restore();
  writes.splice(0);
  throwOnWrite = false;
});

describe("exit extension", () => {
  test("registers /exit command, session_shutdown hook, and one process exit printer", async () => {
    const processPatch = patchProcessExitHooks();
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect([...pi.commands.keys()]).toEqual(["exit"]);
    expect(pi.commands.get("exit")!.description).toBe("Alias for /quit");
    expect([...pi.events.keys()]).toEqual(["session_shutdown"]);
    expect(processPatch.exitListeners).toHaveLength(1);
  });

  test("/exit command delegates to context shutdown", async () => {
    patchProcessExitHooks();
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    let shutdownCount = 0;

    await pi.commands.get("exit")!.handler("ignored", { shutdown: () => { shutdownCount += 1; } });

    expect(shutdownCount).toBe(1);
  });

  test("prints a shell-quoted resume command on quit shutdown", async () => {
    const processPatch = patchProcessExitHooks();
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    await pi.events.get("session_shutdown")![0](
      { reason: "quit" },
      { sessionManager: { getSessionFile: () => "/tmp/pi sessions/it's alive.json" } },
    );
    processPatch.exitListeners[0](0);

    expect(writes).toEqual([
      {
        fd: process.stdout.fd,
        text: "Resume this session:\n  'pi' --session '/tmp/pi sessions/it'\\''s alive.json'\n",
      },
    ]);
    expect(processPatch.offCalls).toEqual([]);
  });

  test("does not print anything when quit shutdown has no session file", async () => {
    const processPatch = patchProcessExitHooks();
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    await pi.events.get("session_shutdown")![0](
      { reason: "quit" },
      { sessionManager: { getSessionFile: () => undefined } },
    );
    processPatch.exitListeners[0](0);

    expect(writes).toEqual([]);
    expect(processPatch.offCalls).toEqual([]);
  });

  test("removes the exit printer for non-quit shutdown reasons", async () => {
    const processPatch = patchProcessExitHooks();
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    await pi.events.get("session_shutdown")![0](
      { reason: "reload" },
      { sessionManager: { getSessionFile: () => "/tmp/session.json" } },
    );

    expect(processPatch.offCalls).toEqual([
      { event: "exit", listener: processPatch.exitListeners[0] },
    ]);
    expect(writes).toEqual([]);
  });

  test("ignores stdout write failures during process exit", async () => {
    const processPatch = patchProcessExitHooks();
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    await pi.events.get("session_shutdown")![0](
      { reason: "quit" },
      { sessionManager: { getSessionFile: () => "/tmp/session.json" } },
    );
    throwOnWrite = true;

    expect(() => processPatch.exitListeners[0](0)).not.toThrow();
    expect(writes).toEqual([]);
  });
});
