import { describe, expect, mock, test } from "bun:test";

type SelectItemLike = { value: string; label: string; description?: string };
type SelectInstance = {
  items: SelectItemLike[];
  selectedIndex: number;
  onSelect?: (item: SelectItemLike) => void;
  onCancel?: () => void;
  handleInput(data: string): void;
};
type InputInstance = {
  focused: boolean;
  onSubmit?: (value: string) => void;
  onEscape?: () => void;
};

const selectInstances: SelectInstance[] = [];
const inputInstances: InputInstance[] = [];

mock.module("@earendil-works/pi-tui", () => ({
  Input: class implements InputInstance {
    focused = false;
    onSubmit?: (value: string) => void;
    onEscape?: () => void;
    constructor() {
      inputInstances.push(this);
    }
    invalidate() {}
    render() {
      return ["<input>"];
    }
    handleInput(data: string) {
      if (data === "escape") this.onEscape?.();
      else this.onSubmit?.(data);
    }
  },
  Key: {
    backspace: "backspace",
    escape: "escape",
    enter: "enter",
    up: "up",
    down: "down",
    ctrl: (key: string) => `ctrl+${key}`,
  },
  matchesKey: (data: string, key: string) => data === key,
  fuzzyFilter: (items: SelectItemLike[], query: string) =>
    items.filter(
      (item) => item.label.includes(query) || item.value.includes(query),
    ),
  SelectList: class implements SelectInstance {
    selectedIndex = 0;
    onSelect?: (item: SelectItemLike) => void;
    onCancel?: () => void;
    constructor(public items: SelectItemLike[]) {
      selectInstances.push(this);
    }
    setSelectedIndex(index: number) {
      this.selectedIndex = index;
    }
    invalidate() {}
    render() {
      return this.items.map((item) => item.label);
    }
    handleInput(data: string) {
      if (data === "escape") this.onCancel?.();
      if (data === "enter") this.onSelect?.(this.items[this.selectedIndex]);
    }
  },
  truncateToWidth: (text: string, width: number) => text.slice(0, width),
}));

mock.module("@earendil-works/pi-coding-agent", () => ({
  getSelectListTheme: () => ({}),
}));

async function loadTuiLib() {
  return await import("./tui");
}

function createCtx(actions: Array<(component: any) => void>) {
  const remaining = [...actions];
  return {
    ui: {
      async custom<TResult>(factory: any): Promise<TResult> {
        const unresolved = Symbol("unresolved");
        let resolved: unknown = unresolved;
        const component = factory(
          { requestRender() {} },
          {
            fg: (_name: string, text: string) => text,
            bold: (text: string) => text,
          },
          {},
          (value: unknown) => {
            resolved = value;
          },
        );
        const action = remaining.shift();
        if (!action) throw new Error("No custom UI action queued");
        action(component);
        return (resolved === unresolved ? undefined : resolved) as TResult;
      },
    },
  };
}

describe("tui helpers", () => {
  test("printableInput accepts bracketed paste and filters control chars", async () => {
    const { printableInput } = await loadTuiLib();

    expect(printableInput("abc")).toBe("abc");
    expect(printableInput("\u001b[A")).toBeNull();
    expect(printableInput("\u001b[200~hello\nworld\u001b[201~")).toBe(
      "helloworld",
    );
  });

  test("selectFuzzy filters printable input and selects the matching item", async () => {
    const { selectFuzzy } = await loadTuiLib();
    const ctx = createCtx([
      (component) => {
        component.handleInput("b");
        const list = selectInstances.at(-1);
        expect(list?.items.map((item) => item.value)).toEqual(["b"]);
        component.handleInput("enter");
      },
    ]);

    await expect(
      selectFuzzy(ctx, {
        title: "Pick",
        items: [
          { value: "a", label: "Alpha" },
          { value: "b", label: "Beta" },
        ],
      }),
    ).resolves.toBe("b");
  });

  test("notifyIfUI delivers only when a UI is attached", async () => {
    const { notifyIfUI } = await loadTuiLib();
    const calls: Array<{ message: string; level?: string }> = [];
    const ctx = (hasUI?: boolean) => ({
      hasUI,
      ui: {
        notify(message: string, level?: string) {
          calls.push({ message, level });
        },
      },
    });

    expect(notifyIfUI(ctx(true), "hi")).toBe(true);
    expect(notifyIfUI(ctx(undefined), "default", "warning")).toBe(true);
    expect(notifyIfUI(ctx(false), "skip")).toBe(false);
    expect(calls).toEqual([
      { message: "hi", level: "info" },
      { message: "default", level: "warning" },
    ]);
  });

  test("widget helpers set belowEditor lines and clear them", async () => {
    const { setBelowEditorWidget, clearWidget } = await loadTuiLib();
    const widgets: Array<{
      key: string;
      content: string[] | undefined;
      options?: unknown;
    }> = [];
    const ctx = {
      ui: {
        setWidget(
          key: string,
          content: string[] | undefined,
          options?: unknown,
        ) {
          widgets.push({ key, content, options });
        },
      },
    };

    setBelowEditorWidget(ctx, "k", ["line"]);
    clearWidget(ctx, "k");
    expect(widgets).toEqual([
      { key: "k", content: ["line"], options: { placement: "belowEditor" } },
      { key: "k", content: undefined, options: undefined },
    ]);
  });

  test("startSpinnerWidget renders elapsed time and clears on stop", async () => {
    const { startSpinnerWidget, SPINNER_FRAMES } = await loadTuiLib();
    const widgets: Array<string[] | undefined> = [];
    const ctx = {
      ui: {
        setWidget(_key: string, content: string[] | undefined) {
          widgets.push(content);
        },
      },
    };
    let clock = 1000;

    const stop = startSpinnerWidget(ctx, "spin", "working", {
      intervalMs: 1_000_000,
      now: () => clock,
    });
    expect(widgets[0]).toEqual([`${SPINNER_FRAMES[0]} working (0s)`]);

    clock = 3500;
    stop();
    expect(widgets.at(-1)).toBeUndefined();
  });

  test("inputOptional trims submitted text and maps escape to null", async () => {
    const { inputOptional } = await loadTuiLib();
    const submitCtx = createCtx([
      () => {
        inputInstances.at(-1)?.onSubmit?.("  hello  ");
      },
    ]);
    const escapeCtx = createCtx([
      () => {
        inputInstances.at(-1)?.onEscape?.();
      },
    ]);

    await expect(
      inputOptional(submitCtx, { title: "Notes", placeholder: "optional" }),
    ).resolves.toBe("hello");
    await expect(
      inputOptional(escapeCtx, { title: "Notes", placeholder: "optional" }),
    ).resolves.toBeNull();
  });
});
