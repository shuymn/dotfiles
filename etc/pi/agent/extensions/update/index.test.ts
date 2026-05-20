import { afterEach, describe, expect, mock, test } from "bun:test";

class MockSettingsManager {
  getQuietStartup() {
    return false;
  }
}

mock.module("@earendil-works/pi-coding-agent", () => ({
  SettingsManager: MockSettingsManager,
}));

type ExecCall = { command: string; args: string[]; options: Record<string, unknown> };
type ExecResult = { code: number; stdout: string; stderr: string };
type EventHandler = (event: any, ctx: FakeContext) => Promise<void> | void;
type FetchResponse = { ok: boolean; status: number; json: () => Promise<unknown> };
type FakeContext = ReturnType<typeof createContext>;

const originalArgv = [...process.argv];
const originalFetch = globalThis.fetch;
const originalConsoleLog = console.log;
const originalConsoleError = console.error;
const originalGetQuietStartup = MockSettingsManager.prototype.getQuietStartup;

function createFakePi(execHandler: (call: ExecCall) => ExecResult | Promise<ExecResult> = defaultExec) {
  const flags = new Map<string, unknown>();
  const registeredFlags: Array<{ name: string; definition: unknown }> = [];
  const events = new Map<string, EventHandler[]>();
  const execCalls: ExecCall[] = [];

  return {
    flags,
    registeredFlags,
    events,
    execCalls,
    registerFlag(name: string, definition: unknown) {
      registeredFlags.push({ name, definition });
    },
    on(eventName: string, handler: EventHandler) {
      events.set(eventName, [...(events.get(eventName) ?? []), handler]);
    },
    getFlag(name: string) {
      return flags.get(name);
    },
    async exec(command: string, args: string[], options: Record<string, unknown> = {}) {
      const call = { command, args, options };
      execCalls.push(call);
      return execHandler(call);
    },
  };
}

function defaultExec(call: ExecCall): ExecResult {
  const args = call.args.join(" ");
  if (call.command === "pi" && args === "--version") return { code: 0, stdout: "pi 1.0.0\n", stderr: "" };
  if (call.command === "bun" && args.startsWith("install --lockfile-only")) return { code: 0, stdout: "lockfile ok", stderr: "" };
  if (call.command === "bun" && args === "audit --audit-level=low") return { code: 0, stdout: "0 vulnerabilities", stderr: "" };
  if (call.command === "bun" && args.startsWith("install -g @earendil-works/pi-coding-agent@")) return { code: 0, stdout: "installed", stderr: "" };
  return { code: 1, stdout: "", stderr: `unexpected command: ${call.command} ${args}` };
}

function createContext(options: { hasUI?: boolean } = {}) {
  const notifications: Array<{ message: string; level: string }> = [];
  let shutdownCount = 0;
  return {
    notifications,
    get shutdownCount() { return shutdownCount; },
    hasUI: options.hasUI ?? true,
    shutdown() { shutdownCount += 1; },
    ui: {
      notify(message: string, level: string) {
        notifications.push({ message, level });
      },
    },
  };
}

function setFetch(handler: (url: string, init?: RequestInit) => FetchResponse | Promise<FetchResponse>) {
  globalThis.fetch = ((url: string | URL | Request, init?: RequestInit) => handler(String(url), init)) as typeof fetch;
}

function latestVersion(version: string): FetchResponse {
  return { ok: true, status: 200, json: async () => ({ version }) };
}

async function loadExtension() {
  return (await import("./index")).default;
}

afterEach(() => {
  process.argv.splice(0, process.argv.length, ...originalArgv);
  globalThis.fetch = originalFetch;
  console.log = originalConsoleLog;
  console.error = originalConsoleError;
  MockSettingsManager.prototype.getQuietStartup = originalGetQuietStartup;
});

describe("update extension", () => {
  test("registers --update flag, session_start hook, and quiet-startup patch for --update argv", async () => {
    process.argv.push("--update");
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect(pi.registeredFlags).toEqual([
      { name: "update", definition: { description: "Update pi with bun and exit", type: "boolean", default: false } },
    ]);
    expect([...pi.events.keys()]).toEqual(["session_start"]);
    expect(new MockSettingsManager().getQuietStartup()).toBe(true);

    process.argv.splice(process.argv.indexOf("--update"), 1);
    expect(new MockSettingsManager().getQuietStartup()).toBe(false);
  });

  test("does nothing unless startup session has update flag", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext();
    setFetch(async () => latestVersion("9.9.9"));

    await pi.events.get("session_start")![0]({ reason: "resume" }, ctx);
    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(pi.execCalls).toEqual([]);
    expect(ctx.notifications).toEqual([]);
    expect(ctx.shutdownCount).toBe(0);
  });

  test("reports already-current version and skips audit/install", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("update", true);
    setFetch((url, init) => {
      expect(url).toBe("https://npm.flatt.tech/@earendil-works%2Fpi-coding-agent/latest");
      expect(init?.signal).toBeInstanceOf(AbortSignal);
      return latestVersion("1.0.0");
    });
    const ctx = createContext();

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(pi.execCalls).toEqual([{ command: "pi", args: ["--version"], options: { timeout: 10_000, cwd: undefined } }]);
    expect(ctx.notifications[0]).toEqual({
      message: "Checking latest @earendil-works/pi-coding-agent version from https://npm.flatt.tech...",
      level: "info",
    });
    expect(ctx.notifications[1]).toEqual({
      message: [
        "pi is already up to date",
        "Package: @earendil-works/pi-coding-agent@1.0.0",
        "Registry: https://npm.flatt.tech",
        "Version: 1.0.0",
        "Action: skipped audit and install.",
      ].join("\n"),
      level: "success",
    });
    expect(ctx.shutdownCount).toBe(1);
  });

  test("audits pinned package, installs latest version, verifies version, and shuts down", async () => {
    const extension = await loadExtension();
    let versionCalls = 0;
    const pi = createFakePi((call) => {
      const args = call.args.join(" ");
      if (call.command === "pi" && args === "--version") {
        versionCalls += 1;
        return { code: 0, stdout: versionCalls === 1 ? "pi 1.0.0\n" : "pi 1.2.3\n", stderr: "" };
      }
      return defaultExec(call);
    });
    extension(pi as never);
    pi.flags.set("update", true);
    setFetch(async () => latestVersion("1.2.3"));
    const ctx = createContext();

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(pi.execCalls.map((call) => [call.command, call.args, typeof call.options.cwd === "string" ? "audit-cwd" : call.options.cwd, call.options.timeout])).toEqual([
      ["pi", ["--version"], undefined, 10_000],
      ["bun", ["install", "--lockfile-only", "--ignore-scripts", "--no-progress", "--registry=https://npm.flatt.tech"], "audit-cwd", 120_000],
      ["bun", ["audit", "--audit-level=low"], "audit-cwd", 120_000],
      ["bun", ["install", "-g", "@earendil-works/pi-coding-agent@1.2.3", "--registry=https://npm.flatt.tech", "--ignore-scripts"], undefined, 120_000],
      ["pi", ["--version"], undefined, 10_000],
    ]);
    expect(ctx.notifications.map((item) => item.level)).toEqual(["info", "info", "info", "success"]);
    expect(ctx.notifications.at(-1)!.message).toBe([
      "pi update completed",
      "Package: @earendil-works/pi-coding-agent@1.2.3",
      "Registry: https://npm.flatt.tech",
      "Audit: passed (bun audit --audit-level=low)",
      "Version: 1.0.0 -> 1.2.3",
      "Next: restart pi to use the updated runtime everywhere.",
    ].join("\n"));
    expect(ctx.shutdownCount).toBe(1);
  });

  test("reports audit setup failures and does not install", async () => {
    const extension = await loadExtension();
    const pi = createFakePi((call) => {
      const args = call.args.join(" ");
      if (call.command === "bun" && args.startsWith("install --lockfile-only")) return { code: 1, stdout: "", stderr: "registry unavailable" };
      return defaultExec(call);
    });
    extension(pi as never);
    pi.flags.set("update", true);
    setFetch(async () => latestVersion("2.0.0"));
    const ctx = createContext();

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(pi.execCalls.map((call) => call.args.join(" "))).not.toContain("install -g @earendil-works/pi-coding-agent@2.0.0 --registry=https://npm.flatt.tech --ignore-scripts");
    expect(ctx.notifications.at(-1)).toEqual({
      message: [
        "pi update failed",
        "Step: audit",
        "Registry: https://npm.flatt.tech",
        "Details:",
        "Audit setup failed:\nregistry unavailable",
      ].join("\n"),
      level: "error",
    });
    expect(ctx.shutdownCount).toBe(1);
  });

  test("reports install failures with command output", async () => {
    const extension = await loadExtension();
    const pi = createFakePi((call) => {
      const args = call.args.join(" ");
      if (call.command === "bun" && args.startsWith("install -g")) return { code: 1, stdout: "install stdout", stderr: "install stderr" };
      return defaultExec(call);
    });
    extension(pi as never);
    pi.flags.set("update", true);
    setFetch(async () => latestVersion("3.0.0"));
    const ctx = createContext();

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(ctx.notifications.at(-1)).toEqual({
      message: ["pi update failed", "Step: install", "Registry: https://npm.flatt.tech", "Details:", "install stdout\ninstall stderr"].join("\n"),
      level: "error",
    });
  });

  test("reports registry errors and invalid metadata during version check", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("update", true);
    setFetch(async () => ({ ok: false, status: 503, json: async () => ({}) }));
    const ctx = createContext();

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(ctx.notifications.at(-1)).toEqual({
      message: ["pi update failed", "Step: version check", "Registry: https://npm.flatt.tech", "Details:", "npm registry returned 503"].join("\n"),
      level: "error",
    });

    const pi2 = createFakePi();
    extension(pi2 as never);
    pi2.flags.set("update", true);
    setFetch(async () => ({ ok: true, status: 200, json: async () => ({ version: "" }) }));
    const ctx2 = createContext();
    await pi2.events.get("session_start")![0]({ reason: "startup" }, ctx2);
    expect(ctx2.notifications.at(-1)!.message).toContain("npm registry response did not include a version");
  });

  test("non-UI mode writes notifications to console streams", async () => {
    const extension = await loadExtension();
    const logs: string[] = [];
    const errors: string[] = [];
    console.log = (message?: unknown) => { logs.push(String(message)); };
    console.error = (message?: unknown) => { errors.push(String(message)); };
    const pi = createFakePi(() => ({ code: 1, stdout: "", stderr: "pi missing" }));
    extension(pi as never);
    pi.flags.set("update", true);
    setFetch(async () => latestVersion("4.0.0"));
    const ctx = createContext({ hasUI: false });

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(logs[0]).toBe("Checking latest @earendil-works/pi-coding-agent version from https://npm.flatt.tech...");
    expect(logs[1]).toBe("Auditing @earendil-works/pi-coding-agent@4.0.0...");
    expect(errors).toEqual([
      [
        "pi update failed",
        "Step: audit",
        "Registry: https://npm.flatt.tech",
        "Details:",
        "Audit setup failed:\npi missing",
      ].join("\n"),
    ]);
    expect(ctx.shutdownCount).toBe(1);
  });

  test("startup update launches only once", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    pi.flags.set("update", true);
    setFetch(async () => latestVersion("1.0.0"));
    const ctx = createContext();

    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);
    await pi.events.get("session_start")![0]({ reason: "startup" }, ctx);

    expect(pi.execCalls).toHaveLength(1);
    expect(ctx.shutdownCount).toBe(1);
  });
});
