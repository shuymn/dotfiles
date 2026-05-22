import { afterEach, describe, expect, mock, test } from "bun:test";
import { mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createFakePi as createSharedFakePi } from "../test-support/fake-pi";
import { installTypeboxMock } from "../test-support/typebox-mock";

installTypeboxMock();

mock.module("@earendil-works/pi-coding-agent", () => ({
  defineTool: (tool: unknown) => tool,
  withFileMutationQueue: async (_path: string, fn: () => Promise<void>) => fn(),
  createBashToolDefinition: () => ({
    async execute(_id: string, params: { command: string }) {
      return { content: [{ type: "text", text: params.command }], details: {} };
    },
    renderCall: () => ({}),
    renderResult: () => ({}),
  }),
}));

type ToolDefinition = {
  name: string;
  label: string;
  description: string;
  promptSnippet?: string;
  promptGuidelines?: string[];
  parameters: unknown;
  prepareArguments?: (args: unknown) => unknown;
  execute: (
    toolCallId: string,
    params: any,
    signal: AbortSignal | undefined,
    onUpdate: unknown,
    ctx: { cwd: string },
  ) => Promise<{
    content: Array<{ type: "text"; text: string }>;
    details: any;
  }>;
};

function createFakePi(activeTools = ["read", "bash", "edit", "write", "todo"]) {
  let tools = [...activeTools];
  const pi = createSharedFakePi<ToolDefinition>();
  return Object.assign(pi, {
    getActiveTools: () => [...tools],
    setActiveTools: (nextTools: string[]) => {
      tools = [...nextTools];
    },
  });
}

async function loadExtension() {
  return (await import("./index")).default;
}

async function createRegisteredPi(activeTools?: string[]) {
  const extension = await loadExtension();
  const pi = activeTools ? createFakePi(activeTools) : createFakePi();
  extension(pi as never);
  return pi;
}

const tempRoots: string[] = [];

async function createTempRoot(prefix = "pi-codex-tools-") {
  const root = await mkdtemp(join(tmpdir(), prefix));
  tempRoots.push(root);
  return root;
}

async function executeApplyPatch(
  pi: ReturnType<typeof createFakePi>,
  cwd: string,
  input: unknown,
) {
  const tool = pi.tools.get("apply_patch")!;
  const params = tool.prepareArguments?.(input) ?? input;
  return pi.tools
    .get("apply_patch")!
    .execute("call", params, undefined, undefined, { cwd });
}

afterEach(async () => {
  await Promise.all(
    tempRoots
      .splice(0)
      .map((root) => rm(root, { recursive: true, force: true })),
  );
});

describe("codex-tools extension", () => {
  test("registers only Codex-facing tools", async () => {
    const pi = await createRegisteredPi();

    expect([...pi.tools.keys()].sort()).toEqual([
      "apply_patch",
      "shell_command",
    ]);
    expect(pi.tools.has("Read")).toBe(false);
    expect(pi.tools.has("Bash")).toBe(false);
    expect(pi.tools.get("shell_command")!).toMatchObject({
      label: "shell_command",
      parameters: {
        type: "object",
        properties: {
          command: { type: "string" },
          workdir: { type: "string", optional: true },
        },
      },
    });
    expect(pi.tools.get("apply_patch")!).toMatchObject({
      label: "apply_patch",
      parameters: {
        type: "object",
        properties: {
          input: { type: "string" },
        },
      },
    });
    expect(pi.tools.get("apply_patch")!.description).toContain(
      '{ "input": "*** Begin Patch\\n...\\n*** End Patch" }',
    );
    expect(pi.tools.get("apply_patch")!.description).not.toContain(
      "must not wrap",
    );
    expect(pi.tools.get("apply_patch")!.promptGuidelines).toContain(
      "Use apply_patch for file edits that fit Codex patch grammar, passing the complete patch as the input string.",
    );
  });

  test.each([
    [[], ["shell_command", "apply_patch"]],
    [
      ["read", "bash", "edit", "write", "grep", "find", "ls"],
      ["shell_command", "apply_patch"],
    ],
    [
      ["read", "bash", "todo"],
      ["todo", "shell_command", "apply_patch"],
    ],
    [
      ["todo", "review", "shell_command", "apply_patch"],
      ["todo", "review", "shell_command", "apply_patch"],
    ],
  ])("session_start activates only Codex tools from %p", async (activeTools, expectedTools) => {
    const pi = await createRegisteredPi(activeTools);
    for (const handler of pi.getEventHandlers("session_start")) {
      await handler(
        { type: "session_start", reason: "startup" },
        { cwd: process.cwd() },
      );
    }

    expect(pi.getActiveTools()).toEqual(expectedTools);
  });

  test("apply_patch edits files with Codex patch grammar", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();
    await writeFile(join(root, "hello.txt"), "hello\nold\n", "utf8");

    const result = await executeApplyPatch(
      pi,
      root,
      "*** Begin Patch\n*** Update File: hello.txt\n@@\n hello\n-old\n+new\n*** End Patch\n",
    );

    expect(await readFile(join(root, "hello.txt"), "utf8")).toBe(
      "hello\nnew\n",
    );
    expect(result.details.changedFiles).toEqual(["hello.txt"]);
    expect(result.content[0].text).toContain("M hello.txt");
  });

  test.each([
    [
      "raw string",
      "*** Begin Patch\n*** Add File: raw.txt\n+raw\n*** End Patch\n",
    ],
    [
      "input object",
      {
        input:
          "*** Begin Patch\n*** Add File: input.txt\n+input\n*** End Patch\n",
      },
    ],
    [
      "patch object",
      {
        patch:
          "*** Begin Patch\n*** Add File: patch.txt\n+patch\n*** End Patch\n",
      },
    ],
  ])("apply_patch accepts %s invocation shape", async (_label, input) => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();

    const result = await executeApplyPatch(pi, root, input);

    expect(result.details.changedFiles).toHaveLength(1);
    expect(result.content[0].text).toContain("A ");
  });

  test.each([
    [
      "markdown fence",
      "*** Begin Patch\n*** Add File: fenced.txt\n+fenced\n*** End Patch\n```\n",
      "```",
    ],
    [
      "unexpected heredoc terminator",
      "*** Begin Patch\n*** Add File: heredoc.txt\n+heredoc\n*** End Patch\nPATCH\n",
      "PATCH",
    ],
  ])("apply_patch reports actual last line for %s boundary contamination", async (_label, input, lastLine) => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();

    await expect(executeApplyPatch(pi, root, input)).rejects.toThrow(
      `actual last line: ${lastLine}`,
    );
  });

  test("apply_patch escapes control characters in boundary diagnostics", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();

    await expect(
      executeApplyPatch(
        pi,
        root,
        "*** Begin Patch\n*** Add File: color.txt\n+color\n*** End Patch\n\u001b[31mPATCH\n",
      ),
    ).rejects.toThrow("actual last line: \\u{001b}[31mPATCH");
  });

  test("apply_patch truncates long boundary diagnostics", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();
    const longLine = "x".repeat(120);

    await expect(
      executeApplyPatch(
        pi,
        root,
        `*** Begin Patch\n*** Add File: long.txt\n+long\n*** End Patch\n${longLine}\n`,
      ),
    ).rejects.toThrow(`${"x".repeat(77)}...`);
  });

  test("apply_patch accepts non-empty Environment ID preamble", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();

    const result = await executeApplyPatch(
      pi,
      root,
      "*** Begin Patch\n*** Environment ID: local\n*** Add File: env.txt\n+env\n*** End Patch\n",
    );

    expect(await readFile(join(root, "env.txt"), "utf8")).toBe("env\n");
    expect(result.details.changedFiles).toEqual(["env.txt"]);
  });

  test("apply_patch rejects empty Environment ID preamble", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();

    await expect(
      executeApplyPatch(
        pi,
        root,
        "*** Begin Patch\n*** Environment ID:   \n*** Add File: env.txt\n+env\n*** End Patch\n",
      ),
    ).rejects.toThrow("environment id cannot be empty");
  });

  test("apply_patch rejects Environment ID outside the preamble", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();
    await writeFile(join(root, "env.txt"), "old\n", "utf8");

    await expect(
      executeApplyPatch(
        pi,
        root,
        "*** Begin Patch\n*** Update File: env.txt\n*** Environment ID: late\n@@\n-old\n+new\n*** End Patch\n",
      ),
    ).rejects.toThrow(
      "Environment ID is only allowed immediately after *** Begin Patch",
    );
  });

  test("apply_patch rejects absolute paths", async () => {
    const pi = await createRegisteredPi();

    await expect(
      executeApplyPatch(
        pi,
        process.cwd(),
        "*** Begin Patch\n*** Add File: /tmp/nope.txt\n+nope\n*** End Patch\n",
      ),
    ).rejects.toThrow("file paths must be relative");
  });

  test("apply_patch rejects parent-directory traversal", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();

    await expect(
      executeApplyPatch(
        pi,
        root,
        "*** Begin Patch\n*** Add File: ../nope.txt\n+nope\n*** End Patch\n",
      ),
    ).rejects.toThrow("file paths must be relative");
  });

  test("apply_patch rejects workspace escape through a symlinked directory", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();
    const outside = await createTempRoot("pi-codex-tools-outside-");
    await symlink(outside, join(root, "linked"), "dir");

    await expect(
      executeApplyPatch(
        pi,
        root,
        "*** Begin Patch\n*** Add File: linked/nope.txt\n+nope\n*** End Patch\n",
      ),
    ).rejects.toThrow("Path escapes workspace");
  });

  test("apply_patch allows Add File to overwrite an existing file", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();
    await writeFile(join(root, "existing.txt"), "existing\n", "utf8");

    const result = await executeApplyPatch(
      pi,
      root,
      "*** Begin Patch\n*** Add File: existing.txt\n+new\n*** End Patch\n",
    );

    expect(await readFile(join(root, "existing.txt"), "utf8")).toBe("new\n");
    expect(result.details.changedFiles).toEqual(["existing.txt"]);
    expect(result.content[0].text).toContain("A existing.txt");
  });

  test("apply_patch allows Move to to overwrite an existing target", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();
    await writeFile(join(root, "existing.txt"), "existing\n", "utf8");
    await writeFile(join(root, "source.txt"), "source\n", "utf8");

    const result = await executeApplyPatch(
      pi,
      root,
      "*** Begin Patch\n*** Update File: source.txt\n*** Move to: existing.txt\n@@\n-source\n+moved\n*** End Patch\n",
    );

    await expect(readFile(join(root, "source.txt"), "utf8")).rejects.toThrow();
    expect(await readFile(join(root, "existing.txt"), "utf8")).toBe("moved\n");
    expect(result.details.changedFiles).toEqual(["existing.txt"]);
    expect(result.content[0].text).toContain("M existing.txt");
  });

  test("apply_patch rejects Move to targets that resolve to the source", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();
    await writeFile(join(root, "source.txt"), "source\n", "utf8");
    await symlink(join(root, "source.txt"), join(root, "alias.txt"));

    await expect(
      executeApplyPatch(
        pi,
        root,
        "*** Begin Patch\n*** Update File: source.txt\n*** Move to: alias.txt\n@@\n-source\n+moved\n*** End Patch\n",
      ),
    ).rejects.toThrow("Cannot move file to itself");
    expect(await readFile(join(root, "source.txt"), "utf8")).toBe("source\n");
  });

  test("apply_patch inserts add-only hunks at the header location", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();
    await writeFile(
      join(root, "sections.txt"),
      "first\nanchor\nsecond\n",
      "utf8",
    );

    await executeApplyPatch(
      pi,
      root,
      "*** Begin Patch\n*** Update File: sections.txt\n@@ anchor\n+inserted\n*** End Patch\n",
    );

    expect(await readFile(join(root, "sections.txt"), "utf8")).toBe(
      "first\nanchor\ninserted\nsecond\n",
    );
  });

  test("apply_patch applies repeated context to the first match", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();
    await writeFile(join(root, "repeated.txt"), "old\nold\n", "utf8");

    await executeApplyPatch(
      pi,
      root,
      "*** Begin Patch\n*** Update File: repeated.txt\n@@\n-old\n+new\n*** End Patch\n",
    );

    expect(await readFile(join(root, "repeated.txt"), "utf8")).toBe(
      "new\nold\n",
    );
  });

  test("apply_patch applies repeated context sequentially across hunks", async () => {
    const pi = await createRegisteredPi();
    const root = await createTempRoot();
    await writeFile(join(root, "repeated.txt"), "old\nold\n", "utf8");

    await executeApplyPatch(
      pi,
      root,
      "*** Begin Patch\n*** Update File: repeated.txt\n@@\n-old\n+first\n@@\n-old\n+second\n*** End Patch\n",
    );

    expect(await readFile(join(root, "repeated.txt"), "utf8")).toBe(
      "first\nsecond\n",
    );
  });
});
