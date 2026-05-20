import { describe, expect, mock, test } from "bun:test";

mock.module("@earendil-works/pi-tui", () => ({
  truncateToWidth: (text: string, width: number, suffix = "") =>
    text.length > width
      ? `${text.slice(0, Math.max(0, width - suffix.length))}${suffix}`
      : text,
}));

type EventHandler = (event: unknown, ctx: FakeContext) => void;
type ShortcutHandler = (ctx: FakeContext) => void;
type BranchEntry = { type: string; customType?: string; data?: unknown };

type FakeContext = ReturnType<typeof createContext>;

function createFakePi() {
  const shortcuts = new Map<
    string,
    { description: string; handler: ShortcutHandler }
  >();
  const events = new Map<string, EventHandler[]>();
  const appendedEntries: Array<{ type: string; data: unknown }> = [];

  return {
    shortcuts,
    events,
    appendedEntries,
    registerShortcut(
      shortcut: string,
      definition: { description: string; handler: ShortcutHandler },
    ) {
      shortcuts.set(shortcut, definition);
    },
    on(eventName: string, handler: EventHandler) {
      events.set(eventName, [...(events.get(eventName) ?? []), handler]);
    },
    appendEntry(type: string, data: unknown) {
      appendedEntries.push({ type, data });
    },
  };
}

function createContext(
  options: { editorText?: string; branch?: BranchEntry[] } = {},
) {
  let editorText = options.editorText ?? "";
  const notifications: Array<{ message: string; level: string }> = [];
  const setEditorTexts: string[] = [];

  return {
    notifications,
    setEditorTexts,
    sessionManager: {
      getBranch: () => options.branch ?? [],
    },
    ui: {
      getEditorText: () => editorText,
      setEditorText(text: string) {
        editorText = text;
        setEditorTexts.push(text);
      },
      notify(message: string, level: string) {
        notifications.push({ message, level });
      },
    },
  };
}

async function loadExtension() {
  return (await import("./index")).default;
}

describe("prompt-stash extension", () => {
  test("registers ctrl+s shortcut and restore lifecycle hooks", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect([...pi.shortcuts.keys()]).toEqual(["ctrl+s"]);
    expect(pi.shortcuts.get("ctrl+s")!.description).toBe(
      "Stash current prompt buffer and clear the editor",
    );
    expect([...pi.events.keys()].sort()).toEqual([
      "agent_start",
      "session_start",
      "user_bash",
    ]);
  });

  test("does not stash blank editor text", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext({ editorText: "  \n\t  " });

    pi.shortcuts.get("ctrl+s")!.handler(ctx);

    expect(ctx.notifications).toEqual([
      { message: "stash する内容がありません。", level: "info" },
    ]);
    expect(ctx.setEditorTexts).toEqual([]);
    expect(pi.appendedEntries).toEqual([]);
  });

  test("stashes current editor text, clears editor, persists state, then restores on next ctrl+s", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext({ editorText: "Please implement feature X" });

    pi.shortcuts.get("ctrl+s")!.handler(ctx);

    expect(ctx.setEditorTexts).toEqual([""]);
    expect(ctx.notifications).toEqual([
      {
        message: "プロンプトを stash しました: Please implement feature X",
        level: "info",
      },
    ]);
    expect(pi.appendedEntries).toEqual([
      {
        type: "prompt-stash-state",
        data: { stack: ["Please implement feature X"] },
      },
    ]);

    pi.shortcuts.get("ctrl+s")!.handler(ctx);

    expect(ctx.setEditorTexts).toEqual(["", "Please implement feature X"]);
    expect(ctx.notifications.at(-1)).toEqual({
      message: "stash を復元しました: Please implement feature X",
      level: "info",
    });
    expect(pi.appendedEntries.at(-1)).toEqual({
      type: "prompt-stash-state",
      data: { stack: [] },
    });
  });

  test("restores latest stashed prompt automatically on agent_start and user_bash", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext({
      branch: [
        {
          type: "custom",
          customType: "prompt-stash-state",
          data: { stack: ["first", "second"] },
        },
      ],
    });

    pi.events.get("session_start")![0]({}, ctx);
    pi.events.get("agent_start")![0]({}, ctx);

    expect(ctx.setEditorTexts).toEqual(["second"]);
    expect(pi.appendedEntries.at(-1)).toEqual({
      type: "prompt-stash-state",
      data: { stack: ["first"] },
    });

    ctx.ui.setEditorText("");
    pi.events.get("user_bash")![0]({}, ctx);

    expect(ctx.setEditorTexts).toEqual(["second", "", "first"]);
    expect(pi.appendedEntries.at(-1)).toEqual({
      type: "prompt-stash-state",
      data: { stack: [] },
    });
  });

  test("does not restore over non-empty editor and keeps stash for later", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext({
      editorText: "current draft",
      branch: [
        {
          type: "custom",
          customType: "prompt-stash-state",
          data: { stack: ["stashed draft"] },
        },
      ],
    });

    pi.events.get("session_start")![0]({}, ctx);
    pi.events.get("agent_start")![0]({}, ctx);

    expect(ctx.notifications).toEqual([
      {
        message: "エディタが空でないため stash を復元しませんでした。",
        level: "warning",
      },
    ]);
    expect(ctx.setEditorTexts).toEqual([]);
    expect(pi.appendedEntries).toEqual([]);

    ctx.ui.setEditorText("");
    pi.shortcuts.get("ctrl+s")!.handler(ctx);

    expect(ctx.setEditorTexts).toEqual(["", "stashed draft"]);
    expect(pi.appendedEntries.at(-1)).toEqual({
      type: "prompt-stash-state",
      data: { stack: [] },
    });
  });

  test("restores the latest valid state entry and filters invalid stack items", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext({
      branch: [
        {
          type: "custom",
          customType: "prompt-stash-state",
          data: { stack: ["old"] },
        },
        {
          type: "message",
          customType: "prompt-stash-state",
          data: { stack: ["ignored message entry"] },
        },
        {
          type: "custom",
          customType: "other",
          data: { stack: ["ignored custom type"] },
        },
        {
          type: "custom",
          customType: "prompt-stash-state",
          data: { stack: ["new", 123, null, "latest"] },
        },
      ],
    });

    pi.events.get("session_start")![0]({}, ctx);
    pi.events.get("agent_start")![0]({}, ctx);

    expect(ctx.setEditorTexts).toEqual(["latest"]);
    expect(pi.appendedEntries.at(-1)).toEqual({
      type: "prompt-stash-state",
      data: { stack: ["new"] },
    });
  });

  test("keeps only the newest twenty stashes when restoring persisted state", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const originalStack = Array.from(
      { length: 25 },
      (_value, index) => `stash-${index + 1}`,
    );
    const ctx = createContext({
      branch: [
        {
          type: "custom",
          customType: "prompt-stash-state",
          data: { stack: originalStack },
        },
      ],
    });

    pi.events.get("session_start")![0]({}, ctx);
    pi.events.get("agent_start")![0]({}, ctx);

    expect(ctx.setEditorTexts).toEqual(["stash-25"]);
    expect(pi.appendedEntries.at(-1)).toEqual({
      type: "prompt-stash-state",
      data: { stack: originalStack.slice(5, 24) },
    });
  });

  test("notice text is whitespace-normalized and truncated", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const longText = `first line\n${"x".repeat(100)}`;
    const ctx = createContext({ editorText: longText });

    pi.shortcuts.get("ctrl+s")!.handler(ctx);

    expect(ctx.notifications[0].message).toBe(
      `プロンプトを stash しました: first line ${"x".repeat(66)}...`,
    );
  });
});
