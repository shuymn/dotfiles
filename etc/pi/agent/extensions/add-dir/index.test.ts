import { afterEach, describe, expect, mock, test } from "bun:test";
import { mkdir, mkdtemp, realpath, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

mock.module("typebox", () => {
  const Type = {
    Object: (properties: Record<string, unknown>, options = {}) => ({
      type: "object",
      properties,
      ...options,
    }),
    String: (options = {}) => ({ type: "string", ...options }),
    Optional: (schema: Record<string, unknown>) => ({
      ...schema,
      optional: true,
    }),
  };
  return { Type };
});

mock.module("@earendil-works/pi-coding-agent", () => ({}));

type NotifyLevel = "info" | "error";
type CommandHandler = (
  args: string,
  ctx: FakeCommandContext,
) => Promise<void> | void;
type EventHandler = (event: any, ctx: any) => Promise<any> | any;
type ToolDefinition = {
  name: string;
  execute: (
    toolCallId: string,
    params: { url: string; directoryName?: string },
    signal: AbortSignal | undefined,
    onUpdate: unknown,
    ctx: { cwd: string },
  ) => Promise<unknown>;
};

type FakeCommandContext = {
  cwd: string;
  ui: { notify: (message: string, level: NotifyLevel) => void };
};

function createFakePi() {
  const commands = new Map<string, { handler: CommandHandler }>();
  const tools = new Map<string, ToolDefinition>();
  const events = new Map<string, EventHandler[]>();
  const appendedEntries: Array<{ type: string; data: unknown }> = [];

  return {
    commands,
    tools,
    events,
    appendedEntries,
    registerCommand(name: string, definition: { handler: CommandHandler }) {
      commands.set(name, definition);
    },
    registerTool(definition: ToolDefinition) {
      tools.set(definition.name, definition);
    },
    on(eventName: string, handler: EventHandler) {
      events.set(eventName, [...(events.get(eventName) ?? []), handler]);
    },
    appendEntry(type: string, data: unknown) {
      appendedEntries.push({ type, data });
    },
  };
}

function createCommandContext(cwd: string) {
  const notifications: Array<{ message: string; level: NotifyLevel }> = [];
  return {
    ctx: {
      cwd,
      ui: {
        notify(message: string, level: NotifyLevel) {
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

async function createTempDir() {
  const root = await mkdtemp(join(tmpdir(), "add-dir-test-"));
  tempDirs.push(root);
  return root;
}

const tempDirs: string[] = [];

afterEach(async () => {
  await Promise.all(
    tempDirs.splice(0).map((dir) => rm(dir, { recursive: true, force: true })),
  );
});

describe("add-dir extension", () => {
  test("registers commands, lifecycle hooks, and github clone tool", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect([...pi.commands.keys()].sort()).toEqual([
      "add-dir",
      "list-dir",
      "remove-dir",
    ]);
    expect([...pi.tools.keys()]).toEqual(["github_clone_workspace"]);
    expect([...pi.events.keys()].sort()).toEqual([
      "before_agent_start",
      "session_shutdown",
      "session_start",
    ]);
  });

  test("adds a real directory, persists canonical state, lists it, and injects agent context", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const cwd = await createTempDir();
    const project = join(cwd, "project");
    await mkdir(project);
    const canonicalProject = await realpath(project);
    await pi.events.get("session_start")![0](
      {},
      { sessionManager: { getEntries: () => [] } },
    );

    const { ctx, notifications } = createCommandContext(cwd);
    await pi.commands.get("add-dir")!.handler("./project", ctx);

    expect(notifications).toEqual([
      {
        message: `Added directory: project: ${canonicalProject}`,
        level: "info",
      },
    ]);
    expect(pi.appendedEntries).toEqual([
      {
        type: "add-dir-state",
        data: { dirs: [{ name: "project", path: canonicalProject }] },
      },
    ]);

    await pi.commands.get("list-dir")!.handler("", ctx);
    expect(notifications.at(-1)).toEqual({
      message: `- project: ${canonicalProject}`,
      level: "info",
    });

    const result = await pi.events.get("before_agent_start")![0]({
      systemPrompt: "base prompt",
    });
    expect(result.systemPrompt).toContain("base prompt");
    expect(result.systemPrompt).toContain(`- project: ${canonicalProject}`);
    expect(result.systemPrompt).toContain(
      "Use absolute paths when reading, searching, or editing files",
    );
  });

  test("does not duplicate an already registered path", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const cwd = await createTempDir();
    const project = join(cwd, "project");
    await mkdir(project);
    const canonicalProject = await realpath(project);
    await pi.events.get("session_start")![0](
      {},
      { sessionManager: { getEntries: () => [] } },
    );

    const { ctx, notifications } = createCommandContext(cwd);
    await pi.commands.get("add-dir")!.handler("project", ctx);
    await pi.commands.get("add-dir")!.handler(canonicalProject, ctx);

    expect(notifications.at(-1)).toEqual({
      message: `Already registered: project: ${canonicalProject}`,
      level: "info",
    });
    expect(pi.appendedEntries).toHaveLength(1);
  });

  test("rejects two different directories with the same registered name", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const cwd = await createTempDir();
    const left = join(cwd, "left", "same-name");
    const right = join(cwd, "right", "same-name");
    await mkdir(left, { recursive: true });
    await mkdir(right, { recursive: true });
    const canonicalLeft = await realpath(left);
    const canonicalRight = await realpath(right);
    await pi.events.get("session_start")![0](
      {},
      { sessionManager: { getEntries: () => [] } },
    );

    const { ctx, notifications } = createCommandContext(cwd);
    await pi.commands.get("add-dir")!.handler("left/same-name", ctx);
    await pi.commands.get("add-dir")!.handler("right/same-name", ctx);

    expect(notifications.at(-1)).toEqual({
      message: `Cannot add ${canonicalRight}: directory name "same-name" is already registered for ${canonicalLeft}. Remove it first with /remove-dir same-name.`,
      level: "error",
    });
    expect(pi.appendedEntries).toHaveLength(1);
  });

  test("removes by name or path and persists the remaining directories", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const cwd = await createTempDir();
    const alpha = join(cwd, "alpha");
    const beta = join(cwd, "beta");
    await mkdir(alpha);
    await mkdir(beta);
    const canonicalAlpha = await realpath(alpha);
    const canonicalBeta = await realpath(beta);
    await pi.events.get("session_start")![0](
      {},
      { sessionManager: { getEntries: () => [] } },
    );

    const { ctx, notifications } = createCommandContext(cwd);
    await pi.commands.get("add-dir")!.handler("alpha", ctx);
    await pi.commands.get("add-dir")!.handler("beta", ctx);
    await pi.commands.get("remove-dir")!.handler("alpha", ctx);

    expect(notifications.at(-1)).toEqual({
      message: `Removed directory. Remaining:\n- beta: ${canonicalBeta}`,
      level: "info",
    });
    expect(pi.appendedEntries.at(-1)).toEqual({
      type: "add-dir-state",
      data: { dirs: [{ name: "beta", path: canonicalBeta }] },
    });

    await pi.commands.get("remove-dir")!.handler(canonicalBeta, ctx);
    expect(notifications.at(-1)).toEqual({
      message: "Removed directory. No additional directories remain.",
      level: "info",
    });
    expect(canonicalAlpha).toEndWith("alpha");
  });

  test("restores only valid session entries and drops stale temporary directories", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const cwd = await createTempDir();
    const existing = join(cwd, "existing");
    await mkdir(existing);
    const canonicalExisting = await realpath(existing);
    const staleTemporary = join(cwd, "missing-temp");
    const stalePermanent = join(cwd, "missing-permanent");

    await pi.events.get("session_start")![0](
      {},
      {
        sessionManager: {
          getEntries: () => [
            {
              type: "custom",
              customType: "different",
              data: { dirs: [{ name: "ignored", path: existing }] },
            },
            {
              type: "custom",
              customType: "add-dir-state",
              data: {
                dirs: [
                  null,
                  { name: "existing", path: canonicalExisting },
                  { name: "bad" },
                  { name: "tmp", path: staleTemporary, temporary: true },
                  { name: "permanent", path: stalePermanent },
                ],
              },
            },
          ],
        },
      },
    );

    const { ctx, notifications } = createCommandContext(cwd);
    await pi.commands.get("list-dir")!.handler("", ctx);

    expect(notifications.at(-1)).toEqual({
      message: [
        `- existing: ${canonicalExisting}`,
        `- permanent: ${stalePermanent}`,
      ].join("\n"),
      level: "info",
    });
  });

  test("cleans restored temporary clone roots on shutdown except reload", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const cwd = await createTempDir();
    const tempRoot = await createTempDir();
    const clone = join(tempRoot, "repo");
    await mkdir(clone);
    await pi.events.get("session_start")![0](
      {},
      {
        sessionManager: {
          getEntries: () => [
            {
              type: "custom",
              customType: "add-dir-state",
              data: {
                dirs: [
                  { name: "repo", path: clone, temporary: true, tempRoot },
                ],
              },
            },
          ],
        },
      },
    );

    await pi.events.get("session_shutdown")![0]({ reason: "reload" });
    await expect(stat(tempRoot)).resolves.toBeTruthy();

    await pi.events.get("session_shutdown")![0]({ reason: "exit" });
    await expect(stat(tempRoot)).rejects.toThrow();
    expect(cwd).toBeString();
  });

  test("github clone tool rejects unsupported URLs and unsafe directory names before cloning", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const cwd = await createTempDir();
    const tool = pi.tools.get("github_clone_workspace")!;

    await expect(
      tool.execute(
        "call",
        { url: "git@github.com:owner/repo.git" },
        undefined,
        undefined,
        { cwd },
      ),
    ).rejects.toThrow(
      "github_clone_workspace only accepts full https://github.com/owner/repo URLs.",
    );
    await expect(
      tool.execute(
        "call",
        { url: "https://example.com/owner/repo" },
        undefined,
        undefined,
        { cwd },
      ),
    ).rejects.toThrow(
      "github_clone_workspace only accepts https://github.com URLs.",
    );
    await expect(
      tool.execute(
        "call",
        { url: "https://github.com/owner/repo", directoryName: "../repo" },
        undefined,
        undefined,
        { cwd },
      ),
    ).rejects.toThrow(
      "Directory name may only contain letters, numbers, '.', '_', and '-'.",
    );
  });
});
