import { afterEach, describe, expect, test } from "bun:test";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  createFakePi as createSharedFakePi,
  type ExecCall,
  type ExecResult,
} from "../test-support/fake-pi";
import { createFakeUi } from "../test-support/fake-ui";
import { installTypeboxMock } from "../test-support/typebox-mock";

installTypeboxMock();

type CommandHandler = (
  args: string,
  ctx: FakeCommandContext,
) => Promise<void> | void;
type ToolDefinition = {
  name: string;
  label: string;
  description: string;
  promptSnippet: string;
  promptGuidelines: string[];
  parameters: unknown;
  execute: (
    toolCallId: string,
    params: { files?: string[]; staged?: boolean; instructions?: string },
    signal: AbortSignal | undefined,
    onUpdate: unknown,
    ctx: { cwd: string },
  ) => Promise<{
    content: Array<{ type: "text"; text: string }>;
    details: unknown;
  }>;
};
type FakeCommandContext = {
  cwd: string;
  waitForIdle: () => Promise<void>;
  ui: { notify: (message: string, level: string) => void };
};

const tempDirs: string[] = [];

function defaultExec(call: ExecCall): ExecResult {
  const args = call.args.join(" ");
  if (call.command === "git" && args === "diff --name-status -z") {
    return {
      code: 0,
      stdout: "M\0src/app.ts\0R100\0old.ts\0new.ts\0",
      stderr: "",
    };
  }
  if (call.command === "git" && args === "diff --cached --name-status -z") {
    return { code: 0, stdout: "A\0src/staged.ts\0M\0src/app.ts\0", stderr: "" };
  }
  if (
    call.command === "git" &&
    args === "ls-files --others --exclude-standard -z"
  ) {
    return { code: 0, stdout: "notes.txt\0", stderr: "" };
  }
  if (call.command === "git" && args === "diff") {
    return { code: 0, stdout: "unstaged diff", stderr: "" };
  }
  if (call.command === "git" && args === "diff --cached") {
    return { code: 0, stdout: "staged diff", stderr: "" };
  }
  if (call.command === "git" && args === "ls-files -z") {
    return { code: 0, stdout: "recent-a.ts\0recent-b.ts\0", stderr: "" };
  }
  return { code: 1, stdout: "", stderr: `unexpected git ${args}` };
}

function createFakePi(
  execHandler: (
    call: ExecCall,
  ) => ExecResult | Promise<ExecResult> = defaultExec,
) {
  return createSharedFakePi<
    ToolDefinition,
    { description: string; handler: CommandHandler }
  >({
    exec: (call) => {
      if (call.command === "git") {
        expect(call.options).toMatchObject({
          cwd: expect.any(String),
          timeout: 10_000,
        });
      }
      return execHandler(call);
    },
  });
}

function createCommandContext(cwd = "/repo") {
  const ui = createFakeUi();
  const waited = { value: false };
  const ctx: FakeCommandContext & {
    notifications: typeof ui.notifications;
    waited: typeof waited;
  } = {
    cwd,
    notifications: ui.notifications,
    waited,
    async waitForIdle() {
      waited.value = true;
    },
    ui,
  };
  return ctx;
}

async function loadExtension() {
  return (await import("./index")).default;
}

async function createTempDir() {
  const dir = await mkdtemp(join(tmpdir(), "simplify-extension-test-"));
  tempDirs.push(dir);
  return dir;
}

afterEach(async () => {
  await Promise.all(
    tempDirs.splice(0).map((dir) => rm(dir, { recursive: true, force: true })),
  );
});

describe("simplify extension", () => {
  test("registers command and tool with schema and guidance", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect([...pi.commands.keys()]).toEqual(["simplify"]);
    expect(pi.commands.get("simplify")!.description).toContain(
      "three parallel subagent reviews",
    );
    const tool = pi.tools.get("simplify")!;
    expect(tool.label).toBe("Simplify");
    expect(tool.promptGuidelines.join("\n")).toContain("reduce duplication");
    expect(tool.parameters).toMatchObject({
      type: "object",
      properties: {
        files: { type: "array", optional: true },
        staged: { type: "boolean", optional: true },
        instructions: { type: "string", optional: true },
      },
    });
  });

  test("tool explicit-file mode normalizes @ paths and ignores git status/diff", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const result = await pi.tools
      .get("simplify")!
      .execute(
        "call",
        { files: ["@src/app.ts", "docs/readme.md"] },
        undefined,
        undefined,
        { cwd: "/repo" },
      );

    expect(pi.execCalls).toEqual([]);
    expect(pi.sentMessages).toHaveLength(1);
    expect(pi.sentMessages[0].options).toEqual({
      deliverAs: "followUp",
      triggerTurn: true,
    });
    const prompt = pi.sentMessages[0].message.content;
    expect(prompt).toContain(
      "Target files:\n- src/app.ts (explicit)\n- docs/readme.md (explicit)",
    );
    expect(prompt).toContain(
      "Explicit file mode: git diff is intentionally ignored",
    );
    expect(prompt).toContain("spawn three subagents in parallel");
    expect(prompt).toContain("Code reuse review");
    expect(prompt).toContain("Code quality review");
    expect(prompt).toContain("Efficiency review");
    expect(prompt).toContain(
      "Write the final response to the user in Japanese.",
    );
    expect(prompt).toContain(
      "target file shell arguments are: 'src/app.ts' 'docs/readme.md'",
    );
    expect(result).toEqual({
      content: [
        {
          type: "text",
          text: "Queued simplify review for 2 file(s):\n- src/app.ts (explicit)\n- docs/readme.md (explicit)",
        },
      ],
      details: {
        targets: [
          { path: "src/app.ts", status: "explicit", source: "explicit" },
          { path: "docs/readme.md", status: "explicit", source: "explicit" },
        ],
      },
    });
  });

  test("tool collects changed, staged, renamed, and untracked targets with diff context", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const result = await pi.tools
      .get("simplify")!
      .execute("call", {}, undefined, undefined, { cwd: "/repo" });

    expect(result.details).toEqual({
      targets: [
        { path: "src/app.ts", status: "M", source: "diff" },
        { path: "new.ts", status: "R100", source: "diff" },
        { path: "src/staged.ts", status: "A", source: "diff" },
        { path: "notes.txt", status: "untracked", source: "diff" },
      ],
    });
    expect(pi.execCalls.map((call) => call.args.join(" "))).toEqual([
      "diff --name-status -z",
      "diff --cached --name-status -z",
      "ls-files --others --exclude-standard -z",
      "diff",
      "diff --cached",
    ]);
    const prompt = pi.sentMessages[0].message.content;
    expect(prompt).toContain("## Unstaged diff\n\nunstaged diff");
    expect(prompt).toContain("## Staged diff\n\nstaged diff");
    expect(prompt).toContain("- new.ts (R100; diff)");
  });

  test("staged mode reviews only cached changes", async () => {
    const extension = await loadExtension();
    const pi = createFakePi((call) => {
      const args = call.args.join(" ");
      if (args === "diff --cached --name-status -z")
        return { code: 0, stdout: "M\0staged-only.ts\0", stderr: "" };
      if (args === "diff --cached")
        return { code: 0, stdout: "cached diff only", stderr: "" };
      return { code: 0, stdout: "", stderr: "" };
    });
    extension(pi as never);

    const result = await pi.tools
      .get("simplify")!
      .execute("call", { staged: true }, undefined, undefined, {
        cwd: "/repo",
      });

    expect(result.details).toEqual({
      targets: [{ path: "staged-only.ts", status: "M", source: "diff" }],
    });
    expect(pi.execCalls.map((call) => call.args.join(" "))).toEqual([
      "diff --cached --name-status -z",
      "diff --cached",
    ]);
    expect(pi.sentMessages[0].message.content).toContain(
      "## Staged diff\n\ncached diff only",
    );
  });

  test("falls back to recently modified tracked files when there are no changes", async () => {
    const extension = await loadExtension();
    const cwd = await createTempDir();
    await writeFile(join(cwd, "recent-a.ts"), "a");
    await new Promise((resolve) => setTimeout(resolve, 5));
    await writeFile(join(cwd, "recent-b.ts"), "b");
    const pi = createFakePi((call) => {
      const args = call.args.join(" ");
      if (
        [
          "diff --name-status -z",
          "diff --cached --name-status -z",
          "ls-files --others --exclude-standard -z",
        ].includes(args)
      ) {
        return { code: 0, stdout: "", stderr: "" };
      }
      if (args === "ls-files -z")
        return {
          code: 0,
          stdout: "recent-a.ts\0missing.ts\0recent-b.ts\0",
          stderr: "",
        };
      return { code: 1, stdout: "", stderr: "unexpected" };
    });
    extension(pi as never);

    const result = await pi.tools
      .get("simplify")!
      .execute("call", {}, undefined, undefined, { cwd });

    expect(result.details).toEqual({
      targets: [
        { path: "recent-b.ts", status: "recent", source: "recent" },
        { path: "recent-a.ts", status: "recent", source: "recent" },
      ],
    });
    expect(pi.execCalls.map((call) => call.args.join(" "))).toEqual([
      "diff --name-status -z",
      "diff --cached --name-status -z",
      "ls-files --others --exclude-standard -z",
      "ls-files -z",
    ]);
    expect(pi.sentMessages[0].message.content).toContain(
      "[No git diff available for these targets; inspect the listed files directly.]",
    );
  });

  test("reports no targets when there are no changes or recent files", async () => {
    const extension = await loadExtension();
    const pi = createFakePi(() => ({ code: 0, stdout: "", stderr: "" }));
    extension(pi as never);

    const result = await pi.tools
      .get("simplify")!
      .execute("call", {}, undefined, undefined, { cwd: "/repo" });

    expect(result).toEqual({
      content: [
        {
          type: "text",
          text: "No changed or recent files found for simplify.",
        },
      ],
      details: { targets: [] },
    });
    expect(pi.sentMessages).toEqual([]);
  });

  test("truncates oversized diff context", async () => {
    const extension = await loadExtension();
    const longDiff = "x".repeat(60_010);
    const pi = createFakePi((call) => {
      const args = call.args.join(" ");
      if (args === "diff --name-status -z")
        return { code: 0, stdout: "M\0big.ts\0", stderr: "" };
      if (
        args === "diff --cached --name-status -z" ||
        args === "ls-files --others --exclude-standard -z"
      )
        return { code: 0, stdout: "", stderr: "" };
      if (args === "diff") return { code: 0, stdout: longDiff, stderr: "" };
      if (args === "diff --cached") return { code: 0, stdout: "", stderr: "" };
      return { code: 1, stdout: "", stderr: "unexpected" };
    });
    extension(pi as never);

    await pi.tools
      .get("simplify")!
      .execute("call", {}, undefined, undefined, { cwd: "/repo" });

    expect(pi.sentMessages[0].message.content).toContain(
      "[diff truncated at 60000 chars; inspect files directly before editing]",
    );
  });

  test("command passes additional instructions after -- into prompt", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createCommandContext();

    await pi.commands
      .get("simplify")!
      .handler("@src/app.ts -- remove duplication only", ctx);

    const prompt = pi.sentMessages[0].message.content;
    expect(prompt).toContain(
      "Additional user instructions:\nremove duplication only",
    );
    expect(prompt).toContain(
      "Apply only findings consistent with the Additional user instructions above",
    );
    expect(
      prompt.match(/Additional user instructions:\nremove duplication only/g),
    ).toHaveLength(4);
    expect(ctx.notifications).toEqual([
      {
        message: "/simplify: 1 件のファイルのレビューをキューに追加しました。",
        level: "info",
      },
    ]);
  });

  test("tool passes additional instructions into prompt", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    await pi.tools
      .get("simplify")!
      .execute(
        "call",
        { files: ["src/app.ts"], instructions: "  prefer project utilities  " },
        undefined,
        undefined,
        { cwd: "/repo" },
      );

    const prompt = pi.sentMessages[0].message.content;
    expect(prompt).toContain(
      "Additional user instructions:\nprefer project utilities",
    );
    expect(prompt).toContain(
      "Apply only findings consistent with the Additional user instructions above",
    );
    expect(
      prompt.match(/Additional user instructions:\nprefer project utilities/g),
    ).toHaveLength(4);
    expect(prompt).not.toContain("  prefer project utilities  ");
  });

  test("command waits for idle, parses args, queues pass, and notifies", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createCommandContext();

    await pi.commands.get("simplify")!.handler("--staged @src/app.ts", ctx);

    expect(ctx.waited.value).toBe(true);
    expect(pi.execCalls).toEqual([]);
    expect(pi.sentMessages[0].message.content).toContain(
      "- src/app.ts (explicit)",
    );
    expect(ctx.notifications).toEqual([
      {
        message: "/simplify: 1 件のファイルのレビューをキューに追加しました。",
        level: "info",
      },
    ]);
  });

  test("command notifies when no targets are available", async () => {
    const extension = await loadExtension();
    const pi = createFakePi(() => ({ code: 0, stdout: "", stderr: "" }));
    extension(pi as never);
    const ctx = createCommandContext();

    await pi.commands.get("simplify")!.handler("", ctx);

    expect(ctx.notifications).toEqual([
      {
        message: "/simplify: 変更または最近のファイルが見つかりませんでした。",
        level: "info",
      },
    ]);
    expect(pi.sentMessages).toEqual([]);
  });
});
