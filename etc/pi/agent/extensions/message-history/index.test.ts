import { beforeEach, describe, expect, mock, test } from "bun:test";

type Entry = { type: string; message?: unknown; timestamp: string };
type SessionMeta = {
  path: string;
  modified: Date;
  cwd?: string;
  name?: string;
};
type ShortcutHandler = (ctx: any) => Promise<void> | void;

type InputInstance = {
  focused: boolean;
  value: string;
  getValue: () => string;
  handleInput: (data: string) => void;
};

const inputInstances: InputInstance[] = [];
const sessions = new Map<string, { entries: Entry[] }>();
let listedSessions: SessionMeta[] = [];

mock.module("@earendil-works/pi-tui", () => ({
  Input: class implements InputInstance {
    focused = false;
    value = "";
    constructor() {
      inputInstances.push(this);
    }
    getValue() {
      return this.value;
    }
    invalidate() {}
    render() {
      return [`input:${this.value}`];
    }
    handleInput(data: string) {
      if (data === "backspace") this.value = this.value.slice(0, -1);
      else this.value += data;
    }
  },
  Key: {
    tab: "tab",
    ctrl: (key: string) => `ctrl-${key}`,
  },
  matchesKey: (data: string, key: string) => data === key,
  fuzzyFilter: (
    items: unknown[],
    query: string,
    getText: (item: unknown) => string,
  ) =>
    items.filter((item) =>
      getText(item).toLowerCase().includes(query.toLowerCase()),
    ),
  // Imported (but unused at runtime here) by lib/tui's selectFuzzy; provide a
  // stub so the static named import resolves.
  SelectList: class {},
  truncateToWidth: (text: string, width: number) => text.slice(0, width),
}));

mock.module("@earendil-works/pi-coding-agent", () => ({
  DynamicBorder: class {
    constructor(private readonly colorize: (text: string) => string) {}
    render(width: number) {
      return [this.colorize("─".repeat(width))];
    }
  },
  SessionManager: {
    listAll: async () => listedSessions,
    open: (path: string) => {
      const session = sessions.get(path);
      if (!session) throw new Error(`missing session: ${path}`);
      return { getEntries: () => session.entries };
    },
  },
}));

function createFakePi() {
  const shortcuts = new Map<
    string,
    { description: string; handler: ShortcutHandler }
  >();
  return {
    shortcuts,
    registerShortcut(
      shortcut: string,
      definition: { description: string; handler: ShortcutHandler },
    ) {
      shortcuts.set(shortcut, definition);
    },
  };
}

function messageEntry(
  content: unknown,
  timestamp: number,
  role = "user",
): Entry {
  return {
    type: "message",
    timestamp: new Date(timestamp).toISOString(),
    message: { role, content, timestamp },
  };
}

function createSessionManager(options: {
  entries: Entry[];
  name?: string;
  file?: string | null;
}) {
  return {
    getEntries: () => options.entries,
    getSessionName: () => options.name,
    getSessionFile: () =>
      options.file === null
        ? undefined
        : (options.file ?? "/sessions/current.json"),
  };
}

function keybindings() {
  return {
    matches(data: string, id: string) {
      return (
        (id === "tui.select.up" && data === "up") ||
        (id === "tui.select.down" && data === "down") ||
        (id === "tui.select.confirm" && data === "enter") ||
        (id === "tui.select.cancel" && data === "escape")
      );
    },
  };
}

function createContext(
  options: {
    hasUI?: boolean;
    cwd?: string;
    sessionManager?: ReturnType<typeof createSessionManager>;
    editorText?: string;
    confirmResult?: boolean;
    drivePicker?: (component: {
      render: (width: number) => string[];
      handleInput: (data: string) => void;
      focused?: boolean;
    }) => string | null | undefined;
  } = {},
) {
  const notifications: Array<{ message: string; level: string }> = [];
  const setEditorTexts: string[] = [];
  const customOptions: unknown[] = [];
  const renders: string[][] = [];
  let confirmCalls = 0;

  return {
    notifications,
    setEditorTexts,
    customOptions,
    renders,
    get confirmCalls() {
      return confirmCalls;
    },
    hasUI: options.hasUI ?? true,
    cwd: options.cwd ?? "/repo",
    sessionManager:
      options.sessionManager ??
      createSessionManager({
        entries: [],
        name: "current",
        file: "/sessions/current.json",
      }),
    ui: {
      notify(message: string, level: string) {
        notifications.push({ message, level });
      },
      async custom(
        factory: (
          tui: unknown,
          theme: unknown,
          keybindings: unknown,
          done: (value: string | null) => void,
        ) => unknown,
        customOption: unknown,
      ) {
        customOptions.push(customOption);
        let doneValue: string | null | undefined;
        const component = factory(
          { requestRender() {} },
          {
            fg: (_color: string, text: string) => text,
            bold: (text: string) => text,
          },
          keybindings(),
          (value: string | null) => {
            doneValue = value;
          },
        ) as {
          render: (width: number) => string[];
          handleInput: (data: string) => void;
          focused?: boolean;
        };
        component.focused = true;
        renders.push(component.render(120));
        const driven = options.drivePicker?.(component);
        if (driven !== undefined) return driven;
        return doneValue ?? null;
      },
      getEditorText() {
        return options.editorText ?? "";
      },
      async confirm() {
        confirmCalls += 1;
        return options.confirmResult ?? true;
      },
      setEditorText(text: string) {
        setEditorTexts.push(text);
      },
    },
  };
}

async function loadExtension() {
  return (await import("./index")).default;
}

beforeEach(() => {
  inputInstances.splice(0);
  sessions.clear();
  listedSessions = [];
});

describe("message-history extension", () => {
  test("registers ctrl+r shortcut with a descriptive handler", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect([...pi.shortcuts.keys()]).toEqual(["ctrl+r"]);
    expect(pi.shortcuts.get("ctrl+r")!.description).toBe(
      "Fuzzy-find previous user messages",
    );
  });

  test("does nothing in non-interactive contexts", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext({ hasUI: false });

    await pi.shortcuts.get("ctrl+r")!.handler(ctx);

    expect(ctx.notifications).toEqual([]);
    expect(ctx.customOptions).toEqual([]);
    expect(ctx.setEditorTexts).toEqual([]);
  });

  test("warns when no previous user messages are found", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext();

    await pi.shortcuts.get("ctrl+r")!.handler(ctx);

    expect(ctx.notifications).toEqual([
      { message: "メッセージ履歴を読み込んでいます...", level: "info" },
      {
        message: "過去のユーザーメッセージが見つかりませんでした",
        level: "warning",
      },
    ]);
    expect(ctx.customOptions).toEqual([]);
  });

  test("collects, sorts, and inserts selected user text from current and past sessions", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const currentEntries = [
      messageEntry("current older", 1000),
      messageEntry("assistant ignored", 3000, "assistant"),
      {
        type: "custom",
        timestamp: new Date(4000).toISOString(),
        message: { role: "user", content: "custom ignored" },
      },
    ];
    sessions.set("/sessions/old.json", {
      entries: [
        messageEntry(
          [
            { type: "text", text: "old text" },
            { type: "image" },
            { type: "tool", text: "ignored" },
          ],
          2000,
        ),
      ],
    });
    sessions.set("/sessions/new.json", {
      entries: [messageEntry("newest message", 5000)],
    });
    sessions.set("/sessions/broken.json", {
      entries: [messageEntry("broken", 6000)],
    });
    listedSessions = [
      {
        path: "/sessions/old.json",
        modified: new Date(100),
        cwd: "/other",
        name: "old",
      },
      {
        path: "/sessions/current.json",
        modified: new Date(999),
        cwd: "/repo",
        name: "current duplicate should be skipped",
      },
      {
        path: "/sessions/missing.json",
        modified: new Date(2000),
        cwd: "/missing",
        name: "missing",
      },
      {
        path: "/sessions/new.json",
        modified: new Date(3000),
        cwd: "/repo",
        name: "new",
      },
    ];
    const ctx = createContext({
      sessionManager: createSessionManager({
        entries: currentEntries,
        name: "current",
        file: "/sessions/current.json",
      }),
      drivePicker: (component) => {
        const initial = component.render(120).join("\n");
        expect(initial).toContain("newest message");
        expect(initial).toContain("old text [image]");
        expect(initial.indexOf("newest message")).toBeLessThan(
          initial.indexOf("old text [image]"),
        );
        component.handleInput("down");
        component.handleInput("enter");
        return undefined;
      },
    });

    await pi.shortcuts.get("ctrl+r")!.handler(ctx);

    expect(ctx.setEditorTexts).toEqual(["old text\n[image]"]);
    expect(ctx.customOptions).toEqual([
      {
        overlay: true,
        overlayOptions: { width: "90%", maxHeight: "80%", anchor: "center" },
      },
    ]);
  });

  test("excludes flag-invoked sessions whose first user message starts with User invoked", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    sessions.set("/sessions/commit.json", {
      entries: [
        messageEntry(
          "User invoked --commit with interactive options: --japanese",
          3000,
        ),
        messageEntry("follow-up from commit session", 2000),
      ],
    });
    sessions.set("/sessions/normal.json", {
      entries: [messageEntry("normal historical message", 1000)],
    });
    listedSessions = [
      {
        path: "/sessions/commit.json",
        modified: new Date(3000),
        cwd: "/repo",
        name: "commit",
      },
      {
        path: "/sessions/normal.json",
        modified: new Date(1000),
        cwd: "/repo",
        name: "normal",
      },
    ];
    const ctx = createContext({
      sessionManager: createSessionManager({
        entries: [messageEntry("current normal message", 4000)],
      }),
      drivePicker: (component) => {
        const rendered = component.render(120).join("\n");
        expect(rendered).toContain("current normal message");
        expect(rendered).toContain("normal historical message");
        expect(rendered).not.toContain("User invoked --commit");
        expect(rendered).not.toContain("follow-up from commit session");
        component.handleInput("enter");
        return undefined;
      },
    });

    await pi.shortcuts.get("ctrl+r")!.handler(ctx);

    expect(ctx.setEditorTexts).toEqual(["current normal message"]);
  });

  test("truncates very long messages before insertion", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const longText = "x".repeat(4010);
    const ctx = createContext({
      sessionManager: createSessionManager({
        entries: [messageEntry(longText, 1000)],
      }),
      drivePicker: (component) => {
        component.handleInput("enter");
        return undefined;
      },
    });

    await pi.shortcuts.get("ctrl+r")!.handler(ctx);

    expect(ctx.setEditorTexts).toEqual([`${"x".repeat(4000)}\n...[truncated]`]);
  });

  test("asks before replacing different existing editor text and respects refusal", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const sessionManager = createSessionManager({
      entries: [messageEntry("selected text", 1000)],
    });
    const refusingCtx = createContext({
      sessionManager,
      editorText: "draft",
      confirmResult: false,
      drivePicker: (component) => {
        component.handleInput("enter");
        return undefined;
      },
    });

    await pi.shortcuts.get("ctrl+r")!.handler(refusingCtx);

    expect(refusingCtx.confirmCalls).toBe(1);
    expect(refusingCtx.setEditorTexts).toEqual([]);

    const sameTextCtx = createContext({
      sessionManager,
      editorText: " selected text ",
      drivePicker: (component) => {
        component.handleInput("enter");
        return undefined;
      },
    });
    await pi.shortcuts.get("ctrl+r")!.handler(sameTextCtx);

    expect(sameTextCtx.confirmCalls).toBe(0);
    expect(sameTextCtx.setEditorTexts).toEqual(["selected text"]);
  });

  test("cancelled picker leaves editor unchanged", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext({
      sessionManager: createSessionManager({
        entries: [messageEntry("selected text", 1000)],
      }),
      drivePicker: (component) => {
        component.handleInput("escape");
        return undefined;
      },
    });

    await pi.shortcuts.get("ctrl+r")!.handler(ctx);

    expect(ctx.setEditorTexts).toEqual([]);
    expect(ctx.confirmCalls).toBe(0);
  });

  test("picker filters by text and cycles all/cwd/session scopes with deduplication", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    sessions.set("/sessions/other-cwd.json", {
      entries: [messageEntry("target from other cwd", 3000)],
    });
    sessions.set("/sessions/same-cwd.json", {
      entries: [
        messageEntry("target from same cwd", 2000),
        messageEntry("target from same cwd", 1000),
      ],
    });
    listedSessions = [
      {
        path: "/sessions/other-cwd.json",
        modified: new Date(3000),
        cwd: "/other",
        name: "other",
      },
      {
        path: "/sessions/same-cwd.json",
        modified: new Date(2000),
        cwd: "/repo/../repo",
        name: "same",
      },
    ];
    const ctx = createContext({
      cwd: "/repo",
      sessionManager: createSessionManager({
        entries: [messageEntry("current session target", 4000)],
        file: "/sessions/current.json",
      }),
      drivePicker: (component) => {
        component.handleInput("target");
        let rendered = component.render(120).join("\n");
        expect(rendered).toContain("target from other cwd");
        expect(rendered).toContain("target from same cwd");
        expect(rendered).toContain("current session target");

        component.handleInput("tab");
        rendered = component.render(120).join("\n");
        expect(rendered).not.toContain("target from other cwd");
        expect(rendered.match(/target from same cwd/g)).toHaveLength(1);
        expect(rendered).toContain("current session target");

        component.handleInput("tab");
        rendered = component.render(120).join("\n");
        expect(rendered).not.toContain("target from same cwd");
        expect(rendered).toContain("current session target");
        component.handleInput("enter");
        return undefined;
      },
    });

    await pi.shortcuts.get("ctrl+r")!.handler(ctx);

    expect(ctx.setEditorTexts).toEqual(["current session target"]);
  });

  test("current-session scope includes fileless current session messages", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext({
      sessionManager: createSessionManager({
        entries: [messageEntry("fileless current target", 1000)],
        file: null,
      }),
      drivePicker: (component) => {
        component.handleInput("target");
        component.handleInput("tab");
        component.handleInput("tab");
        const rendered = component.render(120).join("\n");
        expect(rendered).toContain("fileless current target");
        component.handleInput("enter");
        return undefined;
      },
    });

    await pi.shortcuts.get("ctrl+r")!.handler(ctx);

    expect(ctx.setEditorTexts).toEqual(["fileless current target"]);
  });

  test("falls back to current session if listing all sessions fails", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    listedSessions = undefined as unknown as SessionMeta[];
    const ctx = createContext({
      sessionManager: createSessionManager({
        entries: [messageEntry("current only", 1000)],
      }),
      drivePicker: (component) => {
        component.handleInput("enter");
        return undefined;
      },
    });

    await pi.shortcuts.get("ctrl+r")!.handler(ctx);

    expect(ctx.setEditorTexts).toEqual(["current only"]);
  });
});
