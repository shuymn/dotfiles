import { describe, expect, test } from "bun:test";

import { createFakeUi } from "../test-support/fake-ui";
import { createCustomDriver, installTuiMocks } from "../test-support/tui-mocks";

const { selectInstances, inputInstances } = installTuiMocks();

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

  test("widget helpers set aboveEditor/belowEditor lines and clear them", async () => {
    const { setAboveEditorWidget, setBelowEditorWidget, clearWidget } =
      await loadTuiLib();
    const ui = createFakeUi();
    const ctx = { ui };

    setAboveEditorWidget(ctx, "top", ["status"]);
    setBelowEditorWidget(ctx, "bottom", ["line"]);
    clearWidget(ctx, "bottom");
    expect(ui.widgets).toEqual([
      {
        key: "top",
        lines: ["status"],
        options: { placement: "aboveEditor" },
      },
      {
        key: "bottom",
        lines: ["line"],
        options: { placement: "belowEditor" },
      },
      { key: "bottom", lines: undefined, options: undefined },
    ]);
  });

  test("startSpinnerWidget renders initial elapsed time and clears on stop", async () => {
    const { startSpinnerWidget, SPINNER_FRAMES } = await loadTuiLib();
    const ui = createFakeUi();
    const ctx = { ui };
    let clock = 1000;

    const stop = startSpinnerWidget(ctx, "spin", "working", {
      intervalMs: 1_000_000,
      now: () => clock,
    });
    expect(ui.widgets[0]).toEqual({
      key: "spin",
      lines: [`${SPINNER_FRAMES[0]} working (0s)`],
      options: { placement: "belowEditor" },
    });

    clock = 3500;
    stop();
    expect(ui.widgets.at(-1)).toEqual({
      key: "spin",
      lines: undefined,
      options: undefined,
    });
  });

  test("inputOptional trims submitted text and maps escape to null", async () => {
    const { inputOptional } = await loadTuiLib();
    const submitCtx = {
      ui: {
        custom: createCustomDriver([{ kind: "input", value: "  hello  " }], {
          selectInstances,
          inputInstances,
        }),
      },
    };
    const escapeCtx = {
      ui: {
        custom: createCustomDriver([{ kind: "input", value: null }], {
          selectInstances,
          inputInstances,
        }),
      },
    };

    await expect(
      inputOptional(submitCtx, { title: "Notes", placeholder: "optional" }),
    ).resolves.toBe("hello");
    await expect(
      inputOptional(escapeCtx, { title: "Notes", placeholder: "optional" }),
    ).resolves.toBeNull();
  });
});
