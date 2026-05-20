import { mock } from "bun:test";

export type SelectItemLike = {
  value: string;
  label: string;
  description?: string;
};

export type SelectInstance = {
  items: SelectItemLike[];
  selectedIndex: number;
  onSelect?: (item: SelectItemLike) => void;
  onCancel?: () => void;
};

export type InputInstance = {
  focused: boolean;
  onSubmit?: (value: string) => void;
  onEscape?: () => void;
};

export type CustomAction =
  | { kind: "select"; value: string | null }
  | { kind: "input"; value: string | null };

export type TuiInstances = {
  selectInstances: SelectInstance[];
  inputInstances: InputInstance[];
};

/**
 * Install the pi-tui + pi-coding-agent module mocks used by extensions that
 * drive `selectFuzzy` / `inputOptional` from lib/tui. Returns the instance
 * arrays so tests can inspect or drive the created SelectList/Input fakes.
 *
 * `codingAgent` lets a caller add extra pi-coding-agent exports (e.g.
 * `isToolCallEventType`) on top of the shared `getSelectListTheme` stub.
 */
export function installTuiMocks(
  options: { codingAgent?: Record<string, unknown> } = {},
): TuiInstances {
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
    fuzzyFilter: (items: SelectItemLike[], query?: string) =>
      query
        ? items.filter(
            (item) => item.label.includes(query) || item.value.includes(query),
          )
        : items,
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
    truncateToWidth: (text: string, width: number) =>
      width === undefined ? text : text.slice(0, width),
  }));

  mock.module("@earendil-works/pi-coding-agent", () => ({
    getSelectListTheme: () => ({}),
    ...options.codingAgent,
  }));

  return { selectInstances, inputInstances };
}

/**
 * Build a fake `ctx.ui.custom` that runs the component factory, then drives the
 * most recently created SelectList/Input fake according to the queued actions.
 */
export function createCustomDriver(
  actions: CustomAction[],
  instances: TuiInstances,
) {
  const remaining = [...actions];
  const { selectInstances, inputInstances } = instances;

  return async function custom(
    factory: (
      tui: { requestRender(): void },
      theme: {
        fg(name: string, text: string): string;
        bold(text: string): string;
      },
      keybindings: unknown,
      done: (value: unknown) => void,
    ) => unknown,
  ) {
    const unresolved = Symbol("unresolved");
    let resolved: unknown = unresolved;
    const beforeSelectCount = selectInstances.length;
    const beforeInputCount = inputInstances.length;
    factory(
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
    if (action.kind === "select") {
      const select = selectInstances.slice(beforeSelectCount).at(-1);
      if (!select) throw new Error("Expected SelectList to be created");
      if (action.value === null) select.onCancel?.();
      else {
        const item = select.items.find(
          (candidate) => candidate.value === action.value,
        );
        if (!item)
          throw new Error(
            `No select item for value: ${action.value}. Choices: ${select.items
              .map((item) => item.value)
              .join(", ")}`,
          );
        select.onSelect?.(item);
      }
    } else {
      const input = inputInstances.slice(beforeInputCount).at(-1);
      if (!input) throw new Error("Expected Input to be created");
      if (action.value === null) input.onEscape?.();
      else input.onSubmit?.(action.value);
    }
    if (resolved === unresolved)
      throw new Error("Custom UI action did not resolve via done()");
    return resolved;
  };
}
