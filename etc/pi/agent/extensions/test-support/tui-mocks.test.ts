import { describe, expect, test } from "bun:test";
import { createCustomDriver, installTuiMocks } from "./tui-mocks";

const instances = installTuiMocks();

describe("tui-mocks test support", () => {
  test("createCustomDriver runs the factory and resolves the selected value", async () => {
    const { SelectList } = (await import(
      "@earendil-works/pi-tui"
    )) as unknown as {
      SelectList: new (
        items: unknown[],
      ) => {
        onSelect?: (item: { value: string }) => void;
        onCancel?: () => void;
      };
    };
    const custom = createCustomDriver(
      [{ kind: "select", value: "b" }],
      instances,
    );

    const result = await custom((_tui, _theme, _keybindings, done) => {
      const list = new SelectList([
        { value: "a", label: "A" },
        { value: "b", label: "B" },
      ]);
      list.onSelect = (item) => done(item.value);
      list.onCancel = () => done(null);
      return {};
    });

    expect(result).toBe("b");
  });

  test("createCustomDriver drives Input submit and preserves undefined results", async () => {
    const { Input } = (await import("@earendil-works/pi-tui")) as unknown as {
      Input: new () => {
        onSubmit?: (value: string) => void;
        onEscape?: () => void;
      };
    };
    const submit = createCustomDriver(
      [{ kind: "input", value: "hi" }],
      instances,
    );

    const value = await submit((_tui, _theme, _keybindings, done) => {
      const input = new Input();
      input.onSubmit = (text) => done(text);
      input.onEscape = () => done(null);
      return {};
    });
    expect(value).toBe("hi");

    const undefinedSubmit = createCustomDriver(
      [{ kind: "input", value: "" }],
      instances,
    );
    const undefinedValue = await undefinedSubmit(
      (_tui, _theme, _keybindings, done) => {
        const input = new Input();
        input.onSubmit = () => done(undefined);
        return {};
      },
    );
    expect(undefinedValue).toBeUndefined();
  });

  test("createCustomDriver surfaces missing actions and unresolved actions", async () => {
    const { Input } = (await import("@earendil-works/pi-tui")) as unknown as {
      Input: new () => {
        onSubmit?: (value: string) => void;
      };
    };
    const empty = createCustomDriver([], instances);
    await expect(empty(() => ({}))).rejects.toThrow(
      "No custom UI action queued",
    );

    const unresolved = createCustomDriver(
      [{ kind: "input", value: "ignored" }],
      instances,
    );
    await expect(
      unresolved(() => {
        new Input();
        return {};
      }),
    ).rejects.toThrow("Custom UI action did not resolve via done()");
  });
});
