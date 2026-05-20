import { describe, expect, test } from "bun:test";

import {
  type CliExec,
  cliResultForTool,
  execCli,
  runCli,
  truncateCliOutput,
} from "./cli";

function createExec(result: { code: number; stdout: string; stderr: string }) {
  const calls: Array<{
    command: string;
    args: string[];
    options: { signal?: AbortSignal; timeout: number; cwd?: string };
  }> = [];
  const exec: CliExec = async (command, args, options) => {
    calls.push({ command, args, options });
    return result;
  };
  return { exec, calls };
}

describe("cli shared runner", () => {
  test("passes command, args, timeout, signal, and cwd to exec", async () => {
    const signal = new AbortController().signal;
    const { exec, calls } = createExec({ code: 0, stdout: "ok", stderr: "" });

    const result = await execCli(exec, {
      command: "tool",
      args: ["run"],
      timeout: 123,
      signal,
      cwd: "/repo",
    });

    expect(calls).toEqual([
      {
        command: "tool",
        args: ["run"],
        options: { signal, timeout: 123, cwd: "/repo" },
      },
    ]);
    expect(result).toMatchObject({
      command: ["tool", "run"],
      exitCode: 0,
      stdout: "ok",
      stderr: "",
    });
  });

  test("renders zero exit stdout and stderr", async () => {
    const { exec } = createExec({
      code: 0,
      stdout: "hello\n",
      stderr: "warn\n",
    });

    const result = await runCli(exec, {
      command: "tool",
      args: ["run"],
      timeout: 1000,
      successLabel: "Tool result",
    });

    expect(result.text).toBe("Tool result:\n\nhello\n\nstderr:\nwarn");
  });

  test("throws on non-zero exit", async () => {
    const { exec } = createExec({ code: 2, stdout: "bad", stderr: "nope" });

    await expect(
      runCli(exec, { command: "tool", args: [], timeout: 1000 }),
    ).rejects.toThrow("tool command failed with exit code 2");
  });

  test("parses stdout JSON when requested", async () => {
    const { exec } = createExec({
      code: 0,
      stdout: JSON.stringify({ ok: true }),
      stderr: "",
    });

    const result = await runCli(exec, {
      command: "tool",
      args: [],
      timeout: 1000,
      parseJson: true,
    });

    expect(result.json).toEqual({ ok: true });
    expect(result.text).toContain('"ok": true');
  });

  test("treats invalid JSON as text without json details", async () => {
    const { exec } = createExec({ code: 0, stdout: "not json", stderr: "" });

    const result = await runCli(exec, {
      command: "tool",
      args: [],
      timeout: 1000,
      parseJson: true,
    });

    expect(result.json).toBeUndefined();
    expect(result.text).toBe("tool result:\n\nnot json");
  });

  test("truncates output beyond max chars", () => {
    expect(truncateCliOutput("abcdef", 3, "tool")).toBe(
      "abc\n\n[truncated by tool: 3 chars omitted]",
    );
  });

  test("adds failure hint to thrown exec errors and preserves cause", async () => {
    const cause = new Error("ENOENT");
    const exec: CliExec = async () => {
      throw cause;
    };

    try {
      await runCli(exec, {
        command: "tool",
        args: [],
        timeout: 1000,
        failureHint: "Install tool first.",
      });
      throw new Error("Expected runCli to throw");
    } catch (error) {
      expect(error).toBeInstanceOf(Error);
      expect((error as Error).message).toBe("Install tool first.\n\nENOENT");
      expect((error as Error).cause).toBe(cause);
    }
  });

  test("truncates thrown exec errors before adding failure hint", async () => {
    const exec: CliExec = async () => {
      throw new Error("abcdef");
    };

    await expect(
      runCli(exec, {
        command: "tool",
        args: [],
        timeout: 1000,
        failureHint: "Install tool first.",
        maxOutputChars: 3,
        truncationLabel: "tool",
      }),
    ).rejects.toThrow(
      "Install tool first.\n\nabc\n\n[truncated by tool: 3 chars omitted]",
    );
  });

  test("omits absent JSON from tool result details", async () => {
    const { exec } = createExec({ code: 0, stdout: "not json", stderr: "" });
    const result = await runCli(exec, {
      command: "tool",
      args: ["run"],
      timeout: 1000,
      parseJson: true,
    });

    expect(cliResultForTool(result).details).toEqual({
      command: ["tool", "run"],
      exitCode: 0,
      stdout: "not json",
      stderr: "",
    });
  });

  test("keeps parsed null JSON in tool result details", async () => {
    const { exec } = createExec({ code: 0, stdout: "null", stderr: "" });
    const result = await runCli(exec, {
      command: "tool",
      args: ["run"],
      timeout: 1000,
      parseJson: true,
    });

    expect(cliResultForTool(result).details).toEqual({
      command: ["tool", "run"],
      exitCode: 0,
      stdout: "null",
      stderr: "",
      json: null,
    });
  });

  test("converts rendered result to tool result shape", async () => {
    const { exec } = createExec({ code: 0, stdout: '{"ok":true}', stderr: "" });
    const result = await runCli(exec, {
      command: "tool",
      args: ["run"],
      timeout: 1000,
      parseJson: true,
    });

    expect(cliResultForTool(result)).toEqual({
      content: [{ type: "text", text: result.text }],
      details: {
        command: ["tool", "run"],
        exitCode: 0,
        stdout: '{"ok":true}',
        stderr: "",
        json: { ok: true },
      },
    });
  });
});
