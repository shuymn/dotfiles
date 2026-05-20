import { describe, expect, test } from "bun:test";
import { createFakePi, shutdownFakePis } from "./fake-pi";

describe("createFakePi", () => {
  test("records registered tools, commands, flags, and event handlers", () => {
    const pi = createFakePi({ flags: { staged: true }, thinkingLevel: "high" });
    const firstHandler = () => "first";
    const secondHandler = () => "second";

    pi.registerTool({ name: "review", label: "Review" });
    pi.registerCommand("review", {
      description: "Run review",
      handler: () => {},
    });
    pi.registerFlag("staged", { description: "Use staged files" });
    pi.on("agent_end", firstHandler);
    pi.on("agent_end", secondHandler);

    expect(pi.tools.get("review")).toEqual({ name: "review", label: "Review" });
    expect(pi.getTool("review")).toEqual({ name: "review", label: "Review" });
    expect(pi.commands.get("review")?.description).toBe("Run review");
    expect(pi.getCommand("review")?.description).toBe("Run review");
    expect(pi.getFlag("staged")).toBe(true);
    expect(pi.flagDefinitions.get("staged")).toEqual({
      description: "Use staged files",
    });
    expect(pi.events.get("agent_end")).toEqual([firstHandler, secondHandler]);
    expect(pi.getEventHandlers("agent_end")).toEqual([
      firstHandler,
      secondHandler,
    ]);
    expect(pi.getThinkingLevel()).toBe("high");
  });

  test("records exec calls and delegates to custom exec handler", async () => {
    const pi = createFakePi({
      exec: (call) => ({
        code: 7,
        stdout: call.args.join(","),
        stderr: call.command,
      }),
    });

    await expect(pi.exec("git", ["status"], { cwd: "/repo" })).resolves.toEqual(
      {
        code: 7,
        stdout: "status",
        stderr: "git",
      },
    );
    expect(pi.execCalls).toEqual([
      { command: "git", args: ["status"], options: { cwd: "/repo" } },
    ]);
  });

  test("records sent messages and appended entries", () => {
    const pi = createFakePi();

    pi.sendMessage({ content: "hello" }, { triggerTurn: true });
    pi.appendEntry({ type: "note" }, { source: "test" });

    expect(pi.sentMessages).toEqual([
      { message: { content: "hello" }, options: { triggerTurn: true } },
    ]);
    expect(pi.appendedEntries).toEqual([
      { entry: { type: "note" }, options: { source: "test" } },
    ]);
  });

  test("shutdownFakePis fires session shutdown handlers and clears the list", async () => {
    const calls: unknown[] = [];
    const pi = createFakePi();
    pi.on("session_shutdown", (_event, ctx) => calls.push(ctx));
    const pis = [pi];

    await shutdownFakePis(pis, { cwd: "/repo" });

    expect(calls).toEqual([{ cwd: "/repo" }]);
    expect(pis).toEqual([]);
  });
});
