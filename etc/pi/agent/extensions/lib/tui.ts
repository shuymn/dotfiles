import {
  fuzzyFilter,
  Input,
  Key,
  matchesKey,
  type SelectItem,
  SelectList,
  truncateToWidth,
} from "@earendil-works/pi-tui";

export type UiContext = {
  ui: {
    custom<TResult>(
      factory: (
        tui: { requestRender(): void },
        theme: ThemeLike,
        keybindings: unknown,
        done: (value: TResult) => void,
      ) => unknown,
    ): Promise<TResult>;
  };
};

type ThemeLike = {
  fg(name: string, text: string): string;
  bold(text: string): string;
};

export type NotifyLevel = "info" | "warning" | "error";

type NotifyContext = {
  hasUI?: boolean;
  ui: { notify(message: string, type?: NotifyLevel): void };
};

type WidgetContext = {
  ui: {
    setWidget(
      key: string,
      content: string[] | undefined,
      options?: { placement?: "aboveEditor" | "belowEditor" },
    ): void;
  };
};

export const SPINNER_FRAMES = [
  "⠋",
  "⠙",
  "⠹",
  "⠸",
  "⠼",
  "⠴",
  "⠦",
  "⠧",
  "⠇",
  "⠏",
] as const;

const DEFAULT_SPINNER_INTERVAL_MS = 500;

/**
 * Notify only when a UI is attached. UI-only extensions can call this without
 * guarding on `ctx.hasUI` themselves; headless runs become a no-op.
 * Returns whether the notification was delivered.
 */
export function notifyIfUI(
  ctx: NotifyContext,
  message: string,
  level: NotifyLevel = "info",
): boolean {
  if (ctx.hasUI === false) return false;
  ctx.ui.notify(message, level);
  return true;
}

/** Set a belowEditor widget for long-running progress. */
export function setBelowEditorWidget(
  ctx: WidgetContext,
  key: string,
  lines: string[],
): void {
  ctx.ui.setWidget(key, lines, { placement: "belowEditor" });
}

/** Clear a previously set widget. */
export function clearWidget(ctx: WidgetContext, key: string): void {
  ctx.ui.setWidget(key, undefined);
}

/**
 * Start a belowEditor spinner widget that shows elapsed time, for external
 * CLI / long workflows whose duration is hard to predict.
 * Returns a stop function that clears the widget.
 */
export function startSpinnerWidget(
  ctx: WidgetContext,
  key: string,
  message: string,
  options: { intervalMs?: number; now?: () => number } = {},
): () => void {
  const now = options.now ?? Date.now;
  const intervalMs = options.intervalMs ?? DEFAULT_SPINNER_INTERVAL_MS;
  const startedAt = now();
  let frame = 0;

  const tick = () => {
    const spinner = SPINNER_FRAMES[frame++ % SPINNER_FRAMES.length];
    const elapsed = Math.floor((now() - startedAt) / 1000);
    setBelowEditorWidget(ctx, key, [`${spinner} ${message} (${elapsed}s)`]);
  };

  tick();
  const timer = setInterval(tick, intervalMs);
  (timer as { unref?: () => void }).unref?.();

  return () => {
    clearInterval(timer);
    clearWidget(ctx, key);
  };
}

const ESCAPE = String.fromCharCode(0x1b);
const BRACKETED_PASTE_START = `${ESCAPE}[200~`;
const BRACKETED_PASTE_END = `${ESCAPE}[201~`;

export function normalizeOptional(value?: string): string | undefined {
  return value?.trim() || undefined;
}

export function printableInput(data: string): string | null {
  const isBracketedPaste =
    data.startsWith(BRACKETED_PASTE_START) &&
    data.endsWith(BRACKETED_PASTE_END);
  const raw = isBracketedPaste
    ? data.slice(BRACKETED_PASTE_START.length, -BRACKETED_PASTE_END.length)
    : data;
  if (!isBracketedPaste && raw.includes(ESCAPE)) return null;

  const text = [...raw]
    .filter((char) => {
      const code = char.charCodeAt(0);
      return !(code < 32 || code === 0x7f || (code >= 0x80 && code <= 0x9f));
    })
    .join("");
  return text || null;
}

export function truncateLines(lines: string[], width: number): string[] {
  return lines.map((line) => truncateToWidth(line, width, ""));
}

export function accentBorder(theme: ThemeLike, width: number): string {
  return theme.fg("accent", "─".repeat(Math.max(0, width)));
}

export async function selectFuzzy(
  ctx: UiContext,
  options: {
    title: string;
    items: SelectItem[];
    initialValue?: string;
    searchLabel?: string;
    helpText?: string;
    maxVisibleItems?: number;
  },
): Promise<string | null> {
  // Imported lazily so that consumers using only the lightweight helpers
  // (notifyIfUI / widget / spinner) do not load pi-coding-agent at module
  // import time. Keeping this dynamic lets review/coderabbit-review import
  // lib/tui without mocking pi-coding-agent in their tests.
  const { getSelectListTheme } = await import(
    "@earendil-works/pi-coding-agent"
  );
  return await ctx.ui.custom<string | null>((tui, theme, keybindings, done) => {
    // Honor user tui.select.* keybindings, falling back to default keys.
    const matches = keybindings as
      | { matches?: (data: string, id: string) => boolean }
      | undefined;
    const matchesSelect = (
      data: string,
      id: string,
      fallback: Parameters<typeof matchesKey>[1],
    ): boolean =>
      (matches?.matches?.(data, id) ?? false) || matchesKey(data, fallback);
    let query = "";
    let filteredItems = options.items;
    let list: SelectList;

    const makeList = () => {
      filteredItems = query.trim()
        ? fuzzyFilter(
            options.items,
            query.trim(),
            (item) => `${item.label} ${item.value} ${item.description ?? ""}`,
          )
        : options.items;
      list = new SelectList(
        filteredItems,
        Math.min(
          Math.max(filteredItems.length, 1),
          options.maxVisibleItems ?? 12,
        ),
        getSelectListTheme(),
      );
      const initialIndex = filteredItems.findIndex(
        (item) => item.value === options.initialValue,
      );
      if (initialIndex >= 0) list.setSelectedIndex(initialIndex);
      list.onSelect = (item) => done(item.value);
      list.onCancel = () => done(null);
    };

    makeList();

    return {
      invalidate: () => list.invalidate(),
      render: (width: number) =>
        truncateLines(
          [
            accentBorder(theme, width),
            theme.fg("accent", theme.bold(options.title)),
            theme.fg(
              "dim",
              `${options.searchLabel ?? "検索"}: ${query || "(入力して絞り込み)"}`,
            ),
            ...list.render(width),
            truncateToWidth(
              theme.fg(
                "dim",
                options.helpText ??
                  "入力で検索 • ↑↓で移動 • enterで選択 • escで戻る/キャンセル",
              ),
              width,
              "",
            ),
            accentBorder(theme, width),
          ],
          width,
        ),
      handleInput: (data: string) => {
        if (
          matchesKey(data, Key.backspace) ||
          matchesKey(data, Key.ctrl("h"))
        ) {
          query = [...query].slice(0, -1).join("");
          makeList();
          tui.requestRender();
          return;
        }
        if (matchesSelect(data, "tui.select.cancel", Key.escape)) {
          done(null);
          return;
        }
        if (
          matchesSelect(data, "tui.select.confirm", Key.enter) ||
          matchesSelect(data, "tui.select.up", Key.up) ||
          matchesSelect(data, "tui.select.down", Key.down)
        ) {
          list.handleInput(data);
          tui.requestRender();
          return;
        }
        const printable = printableInput(data);
        if (printable) {
          query += printable;
          makeList();
          tui.requestRender();
          return;
        }
        list.handleInput(data);
        tui.requestRender();
      },
    };
  });
}

export async function inputOptional(
  ctx: UiContext,
  options: {
    title: string;
    placeholder: string;
    helpText?: string;
  },
): Promise<string | null | undefined> {
  return await ctx.ui.custom<string | null | undefined>(
    (tui, theme, _keybindings, done) => {
      const input = new Input();
      input.focused = true;
      input.onSubmit = (value) => done(normalizeOptional(value));
      input.onEscape = () => done(null);

      return {
        invalidate: () => input.invalidate(),
        render: (width: number) =>
          truncateLines(
            [
              accentBorder(theme, width),
              theme.fg("accent", theme.bold(options.title)),
              theme.fg("dim", options.placeholder),
              ...input.render(width),
              truncateToWidth(
                theme.fg("dim", options.helpText ?? "enterで確定 • escで戻る"),
                width,
                "",
              ),
              accentBorder(theme, width),
            ],
            width,
          ),
        handleInput: (data: string) => {
          input.handleInput(data);
          tui.requestRender();
        },
      };
    },
  );
}
