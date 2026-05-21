import { describe, expect, mock, test } from "bun:test";
import { createFakePi } from "../test-support/fake-pi";
import { createFakeUi } from "../test-support/fake-ui";

mock.module("typebox", () => ({
  Type: {
    Object: (properties: Record<string, unknown>, options = {}) => ({
      type: "object",
      properties,
      ...options,
    }),
    String: (options = {}) => ({ type: "string", ...options }),
    Number: (options = {}) => ({ type: "number", ...options }),
    Optional: (schema: Record<string, unknown>) => ({
      ...schema,
      optional: true,
    }),
  },
}));

mock.module("@earendil-works/pi-ai", () => ({
  StringEnum: (values: readonly string[], options = {}) => ({
    enum: values,
    ...options,
  }),
}));

mock.module("@earendil-works/pi-coding-agent", () => ({}));

type ToolDefinition = {
  name: string;
  promptSnippet?: string;
  promptGuidelines?: string[];
  execute: (
    toolCallId: string,
    params: any,
    signal?: AbortSignal,
    onUpdate?: unknown,
    ctx?: any,
  ) => Promise<any>;
};

async function loadExtension() {
  return (await import("./index")).default;
}

describe("todo extension", () => {
  test("registers todo tool and lifecycle hooks without slash commands", async () => {
    const extension = await loadExtension();
    const pi = createFakePi<ToolDefinition>();
    extension(pi as never);

    expect([...pi.tools.keys()]).toEqual(["todo"]);
    expect([...pi.commands.keys()]).toEqual([]);
    expect([...pi.getEventHandlers("session_start")]).toHaveLength(1);
    expect([...pi.getEventHandlers("session_tree")]).toHaveLength(1);
    expect([...pi.getEventHandlers("session_compact")]).toHaveLength(1);
    expect([...pi.getEventHandlers("context")]).toHaveLength(1);
    expect(pi.tools.get("todo")!.promptGuidelines!.join("\n")).toContain(
      "Before starting implementation",
    );
  });

  test("tool mutates state, records details snapshot, and refreshes aboveEditor widget", async () => {
    const extension = await loadExtension();
    const pi = createFakePi<ToolDefinition>();
    extension(pi as never);
    const ui = createFakeUi();
    const ctx = { hasUI: true, ui };
    const tool = pi.tools.get("todo")!;

    const created = await tool.execute(
      "call",
      { action: "create", title: "A" },
      undefined,
      undefined,
      ctx,
    );
    expect(created.details.state.items[0].title).toBe("A");
    expect(ui.widgets.at(-1)).toMatchObject({
      key: "todo",
      options: { placement: "aboveEditor" },
    });

    const updated = await tool.execute(
      "call",
      { action: "update", id: 1, status: "in_progress" },
      undefined,
      undefined,
      ctx,
    );
    expect(updated.details.state.items[0].status).toBe("in_progress");
  });

  test("session lifecycle replays branch state and context injects reminder", async () => {
    const extension = await loadExtension();
    const pi = createFakePi<ToolDefinition>();
    extension(pi as never);
    const ui = createFakeUi();
    const snapshot = {
      nextId: 2,
      items: [
        {
          id: 1,
          title: "Replay me",
          status: "pending",
          createdAt: 1,
          updatedAt: 1,
        },
      ],
    };

    await pi.getEventHandlers("session_start")[0](
      {},
      {
        hasUI: true,
        ui,
        sessionManager: {
          getBranch: () => [
            {
              type: "message",
              message: {
                role: "toolResult",
                toolName: "todo",
                details: { state: snapshot },
              },
            },
          ],
        },
      },
    );
    expect(ui.widgets.at(-1)?.lines?.join("\n")).toContain("Replay me");

    const result = (await pi.getEventHandlers("context")[0]({
      messages: [{ role: "user", content: "x" }],
    })) as { messages: Array<{ content: unknown }> };
    expect(result.messages).toHaveLength(2);
    expect(JSON.stringify(result.messages[1].content)).toContain("Replay me");
  });

  test("tool result text guides no-active and active transitions", async () => {
    const extension = await loadExtension();
    const pi = createFakePi<ToolDefinition>();
    extension(pi as never);
    const ui = createFakeUi();
    const ctx = { hasUI: true, ui };
    const tool = pi.tools.get("todo")!;

    const created = await tool.execute(
      "call",
      { action: "create", title: "A" },
      undefined,
      undefined,
      ctx,
    );
    expect(created.content[0].text).toContain(
      "No todo is in_progress. Pick one pending todo and mark it in_progress before continuing.",
    );

    const listed = await tool.execute(
      "call",
      { action: "list" },
      undefined,
      undefined,
      ctx,
    );
    expect(listed.content[0].text).toContain(
      "No todo is in_progress. Pick one pending todo and mark it in_progress before continuing.",
    );

    const active = await tool.execute(
      "call",
      { action: "update", id: 1, status: "in_progress" },
      undefined,
      undefined,
      ctx,
    );
    expect(active.content[0].text).not.toContain("Pick one pending todo");

    const second = await tool.execute(
      "call",
      { action: "create", title: "B" },
      undefined,
      undefined,
      ctx,
    );
    expect(second.content[0].text).not.toContain("Pick one pending todo");

    const completed = await tool.execute(
      "call",
      { action: "update", id: 1, status: "completed" },
      undefined,
      undefined,
      ctx,
    );
    expect(completed.content[0].text).toContain("Next pending todos remain:");
  });

  test("completion reminder does not ask to pick pending when another todo is active", async () => {
    const extension = await loadExtension();
    const pi = createFakePi<ToolDefinition>();
    extension(pi as never);
    const ui = createFakeUi();
    const ctx = { hasUI: true, ui };
    const tool = pi.tools.get("todo")!;

    await tool.execute(
      "call",
      { action: "create", title: "A" },
      undefined,
      undefined,
      ctx,
    );
    await tool.execute(
      "call",
      { action: "create", title: "B" },
      undefined,
      undefined,
      ctx,
    );
    await tool.execute(
      "call",
      { action: "create", title: "C" },
      undefined,
      undefined,
      ctx,
    );
    await tool.execute(
      "call",
      { action: "update", id: 2, status: "in_progress" },
      undefined,
      undefined,
      ctx,
    );
    const completedNonActive = await tool.execute(
      "call",
      { action: "update", id: 1, status: "completed" },
      undefined,
      undefined,
      ctx,
    );

    expect(completedNonActive.content[0].text).not.toContain(
      "Pick one pending todo and mark it in_progress before continuing.",
    );
  });

  test("clear action reports count and clears widget", async () => {
    const extension = await loadExtension();
    const pi = createFakePi<ToolDefinition>();
    extension(pi as never);
    const ui = createFakeUi();
    const ctx = { hasUI: true, ui };
    const tool = pi.tools.get("todo")!;

    await tool.execute(
      "call",
      { action: "create", title: "A" },
      undefined,
      undefined,
      ctx,
    );
    const cleared = await tool.execute(
      "call",
      { action: "clear" },
      undefined,
      undefined,
      ctx,
    );

    expect(cleared.content[0].text).toContain("Cleared 1 todo.");
    expect(ui.widgets.at(-1)).toEqual({ key: "todo", lines: undefined });
  });

  test("session shutdown clears widget and non-UI widget refresh is a no-op", async () => {
    const extension = await loadExtension();
    const pi = createFakePi<ToolDefinition>();
    extension(pi as never);
    const ui = createFakeUi();

    await pi.getEventHandlers("session_shutdown")[0]({}, { hasUI: true, ui });
    expect(ui.widgets.at(-1)).toEqual({ key: "todo", lines: undefined });

    await expect(
      pi.tools
        .get("todo")!
        .execute(
          "call",
          { action: "create", title: "A" },
          undefined,
          undefined,
          {
            hasUI: false,
          },
        ),
    ).resolves.toBeTruthy();
    expect(ui.widgets).toHaveLength(1);
    await expect(
      pi.getEventHandlers("session_shutdown")[0]({}, undefined),
    ).resolves.toBeUndefined();
  });

  test("tool_execution_end refreshes widget for todo results", async () => {
    const extension = await loadExtension();
    const pi = createFakePi<ToolDefinition>();
    extension(pi as never);
    const ui = createFakeUi();
    await pi.tools
      .get("todo")!
      .execute("call", { action: "create", title: "A" }, undefined, undefined, {
        hasUI: true,
        ui,
      });
    const before = ui.widgets.length;
    await pi.getEventHandlers("tool_execution_end")[0](
      { toolName: "todo", isError: false },
      { hasUI: true, ui },
    );
    expect(ui.widgets.length).toBe(before + 1);
  });
});
