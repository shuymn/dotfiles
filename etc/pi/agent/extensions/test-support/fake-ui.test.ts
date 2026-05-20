import { describe, expect, test } from "bun:test";
import { createFakeUi } from "./fake-ui";

describe("createFakeUi", () => {
  test("records notifications and widgets", () => {
    const ui = createFakeUi();

    ui.notify("Done", "info");
    ui.setWidget("review", ["running"], { placement: "belowEditor" });
    ui.setWidget("review", undefined);

    expect(ui.notifications).toEqual([{ message: "Done", level: "info" }]);
    expect(ui.widgets).toEqual([
      {
        key: "review",
        lines: ["running"],
        options: { placement: "belowEditor" },
      },
      { key: "review", lines: undefined, options: undefined },
    ]);
  });

  test("returns queued select, confirm, input, and custom values", async () => {
    const ui = createFakeUi({
      selects: ["all"],
      confirms: [true],
      inputs: ["main"],
      customs: [{ ok: true }],
      editorText: "selected text",
    });

    await expect(ui.select()).resolves.toBe("all");
    await expect(ui.select()).resolves.toBeUndefined();
    await expect(ui.confirm()).resolves.toBe(true);
    await expect(ui.confirm()).resolves.toBe(false);
    await expect(ui.input()).resolves.toBe("main");
    await expect(ui.input()).resolves.toBeUndefined();
    await expect(ui.custom("dialog", { title: "Pick" })).resolves.toEqual({
      ok: true,
    });

    expect(ui.editorText).toBe("selected text");
    expect(ui.customCalls).toEqual([{ args: ["dialog", { title: "Pick" }] }]);
  });
});
