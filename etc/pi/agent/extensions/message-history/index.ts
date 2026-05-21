import { resolve } from "node:path";
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { SessionManager } from "@earendil-works/pi-coding-agent";
import {
  type Component,
  type Focusable,
  fuzzyFilter,
  Input,
  Key,
  matchesKey,
  truncateToWidth,
} from "@earendil-works/pi-tui";
import { accentBorder, truncateLines } from "../lib/tui";

const MAX_SESSIONS_TO_SCAN = 200;
const MAX_MESSAGES_TO_SHOW = 1000;
const MAX_MESSAGE_CHARS = 4000;
const FLAG_INVOCATION_PREFIX = "User invoked";

type HistoryMessage = {
  text: string;
  timestamp: number;
  cwd?: string;
  sessionName?: string;
  sessionPath?: string;
  isCurrentSession?: boolean;
};

type SearchScope = "all" | "cwd" | "session";

function sameResolvedPath(
  a: string | undefined,
  b: string | undefined,
): boolean {
  return a !== undefined && b !== undefined && resolve(a) === b;
}

function userMessageText(message: unknown): string | undefined {
  const msg = message as { role?: string; content?: unknown };
  if (msg.role !== "user") return undefined;

  if (typeof msg.content === "string") return msg.content.trim();

  if (Array.isArray(msg.content)) {
    const parts = msg.content
      .map((block) => {
        const b = block as { type?: string; text?: string };
        if (b.type === "text" && typeof b.text === "string") return b.text;
        if (b.type === "image") return "[image]";
        return undefined;
      })
      .filter((part): part is string => Boolean(part));

    const text = parts.join("\n").trim();
    return text.length > 0 ? text : undefined;
  }

  return undefined;
}

function isFlagInvocationSession(
  entries: ReturnType<ExtensionContext["sessionManager"]["getEntries"]>,
): boolean {
  for (const entry of entries) {
    if (entry.type !== "message") continue;
    const text = userMessageText(entry.message);
    if (text === undefined) continue;
    return text.startsWith(FLAG_INVOCATION_PREFIX);
  }
  return false;
}

function displaySnippet(text: string): string {
  const oneLine = text.replace(/\s+/g, " ").trim();
  return oneLine.length > 180 ? `${oneLine.slice(0, 177)}...` : oneLine;
}

function formatDescription(item: HistoryMessage): string {
  const date = new Date(item.timestamp || Date.now());
  const when = Number.isNaN(date.getTime())
    ? "unknown time"
    : date.toLocaleString();
  const source =
    item.sessionName || item.cwd || item.sessionPath || "current session";
  return `${when} · ${source}`;
}

function collectFromEntries(
  entries: ReturnType<ExtensionContext["sessionManager"]["getEntries"]>,
  meta: Pick<
    HistoryMessage,
    "cwd" | "sessionName" | "sessionPath" | "isCurrentSession"
  > = {},
): HistoryMessage[] {
  if (isFlagInvocationSession(entries)) return [];

  const messages: HistoryMessage[] = [];
  for (const entry of entries) {
    if (entry.type !== "message") continue;
    const text = userMessageText(entry.message);
    if (!text) continue;

    messages.push({
      text:
        text.length > MAX_MESSAGE_CHARS
          ? `${text.slice(0, MAX_MESSAGE_CHARS)}\n...[truncated]`
          : text,
      timestamp:
        Number((entry.message as { timestamp?: number }).timestamp) ||
        Date.parse(entry.timestamp),
      ...meta,
    });
  }
  return messages;
}

async function collectHistoryMessages(
  ctx: ExtensionContext,
): Promise<HistoryMessage[]> {
  const messages: HistoryMessage[] = [];

  messages.push(
    ...collectFromEntries(ctx.sessionManager.getEntries(), {
      cwd: ctx.cwd,
      sessionName: ctx.sessionManager.getSessionName(),
      sessionPath: ctx.sessionManager.getSessionFile(),
      isCurrentSession: true,
    }),
  );

  try {
    const sessions = (await SessionManager.listAll()).sort(
      (a, b) => b.modified.getTime() - a.modified.getTime(),
    );
    for (const session of sessions.slice(0, MAX_SESSIONS_TO_SCAN)) {
      if (session.path === ctx.sessionManager.getSessionFile()) continue;
      try {
        const sm = SessionManager.open(session.path);
        messages.push(
          ...collectFromEntries(sm.getEntries(), {
            cwd: session.cwd,
            sessionName: session.name,
            sessionPath: session.path,
          }),
        );
      } catch {
        // Ignore broken or concurrently modified session files.
      }
    }
  } catch {
    // Fall back to the current session only.
  }

  return messages
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, MAX_MESSAGES_TO_SHOW);
}

class MessageHistoryPicker implements Component, Focusable {
  private input = new Input();
  private selectedIndex = 0;
  private filtered: HistoryMessage[];
  private scope: SearchScope = "all";
  private readonly currentCwdResolved: string;
  private readonly currentSessionPathResolved: string | undefined;
  private readonly scopedItemsCache = new Map<SearchScope, HistoryMessage[]>();

  constructor(
    private readonly items: HistoryMessage[],
    currentCwd: string,
    currentSessionPath: string | undefined,
    private readonly theme: {
      fg(color: string, text: string): string;
      bold(text: string): string;
    },
    private readonly keybindings: {
      matches(data: string, id: string): boolean;
    },
    private readonly done: (value: string | null) => void,
    private readonly requestRender: () => void,
  ) {
    this.currentCwdResolved = resolve(currentCwd);
    this.currentSessionPathResolved = currentSessionPath
      ? resolve(currentSessionPath)
      : undefined;
    this.filtered = items;
  }

  get focused(): boolean {
    return this.input.focused;
  }

  set focused(value: boolean) {
    this.input.focused = value;
  }

  invalidate(): void {
    this.input.invalidate();
  }

  render(width: number): string[] {
    const lines: string[] = [];
    lines.push(accentBorder(this.theme, width));
    lines.push(
      truncateToWidth(
        this.theme.fg(
          "accent",
          this.theme.bold("過去のユーザーメッセージを検索"),
        ),
        width,
      ),
    );
    lines.push(
      this.theme.fg(
        "dim",
        `  範囲: ${this.scope === "all" ? "すべてのメッセージ" : this.scope === "cwd" ? "現在のディレクトリのみ" : "現在のセッションのみ"} · Tabで切替`,
      ),
    );
    lines.push(...this.input.render(width));
    lines.push("");

    if (this.filtered.length === 0) {
      lines.push(this.theme.fg("warning", "  一致するメッセージがありません"));
    } else {
      const maxVisible = Math.max(1, Math.min(12, this.filtered.length));
      const start = Math.max(
        0,
        Math.min(
          this.selectedIndex - Math.floor(maxVisible / 2),
          this.filtered.length - maxVisible,
        ),
      );
      const end = Math.min(start + maxVisible, this.filtered.length);

      for (let i = start; i < end; i++) {
        const item = this.filtered[i];
        if (!item) continue;
        const selected = i === this.selectedIndex;
        const prefix = selected ? "→ " : "  ";
        const snippet = displaySnippet(item.text);
        const line = prefix + snippet;
        lines.push(
          selected
            ? truncateToWidth(this.theme.fg("accent", line), width)
            : truncateToWidth(line, width),
        );

        if (selected) {
          lines.push(
            truncateToWidth(
              this.theme.fg("dim", `    ${formatDescription(item)}`),
              width,
            ),
          );
        }
      }

      if (start > 0 || end < this.filtered.length) {
        lines.push(
          this.theme.fg(
            "dim",
            truncateToWidth(
              `  (${this.selectedIndex + 1}/${this.filtered.length})`,
              width,
            ),
          ),
        );
      }
    }

    lines.push("");
    lines.push(
      this.theme.fg(
        "dim",
        "  入力で絞り込み · ↑↓/Ctrl-JKで移動 · Enterで挿入 · Escでキャンセル",
      ),
    );
    lines.push(accentBorder(this.theme, width));
    return truncateLines(lines, width);
  }

  handleInput(data: string): void {
    if (matchesKey(data, Key.tab)) {
      this.scope =
        this.scope === "all" ? "cwd" : this.scope === "cwd" ? "session" : "all";
      this.applyFilter();
      this.requestRender();
      return;
    }

    if (
      this.keybindings.matches(data, "tui.select.up") ||
      matchesKey(data, Key.ctrl("k"))
    ) {
      this.moveSelection(-1);
      this.requestRender();
      return;
    }

    if (
      this.keybindings.matches(data, "tui.select.down") ||
      matchesKey(data, Key.ctrl("j"))
    ) {
      this.moveSelection(1);
      this.requestRender();
      return;
    }

    if (this.keybindings.matches(data, "tui.select.confirm")) {
      const item = this.filtered[this.selectedIndex];
      this.done(item?.text ?? null);
      return;
    }

    if (this.keybindings.matches(data, "tui.select.cancel")) {
      this.done(null);
      return;
    }

    this.input.handleInput(data);
    this.applyFilter();
    this.requestRender();
  }

  private moveSelection(delta: number): void {
    if (this.filtered.length === 0) return;
    const next = this.selectedIndex + delta;
    this.selectedIndex =
      next < 0
        ? this.filtered.length - 1
        : next >= this.filtered.length
          ? 0
          : next;
  }

  private getScopedItems(): HistoryMessage[] {
    const cached = this.scopedItemsCache.get(this.scope);
    if (cached) return cached;

    const scopedItems = this.items.filter((item) => {
      if (this.scope === "cwd") {
        return sameResolvedPath(item.cwd, this.currentCwdResolved);
      }
      if (this.scope === "session") {
        return (
          item.isCurrentSession ||
          sameResolvedPath(item.sessionPath, this.currentSessionPathResolved)
        );
      }
      return true;
    });

    const uniqueItems: HistoryMessage[] = [];
    const seen = new Set<string>();
    for (const item of scopedItems) {
      const key = item.text.trim();
      if (!key || seen.has(key)) continue;
      seen.add(key);
      uniqueItems.push(item);
    }

    this.scopedItemsCache.set(this.scope, uniqueItems);
    return uniqueItems;
  }

  private applyFilter(): void {
    const query = this.input.getValue().trim();
    const scopedItems = this.getScopedItems();
    this.filtered =
      query.length === 0
        ? scopedItems
        : fuzzyFilter(scopedItems, query, (item) => item.text);
    this.selectedIndex = 0;
  }
}

async function openMessageHistory(ctx: ExtensionContext): Promise<void> {
  if (!ctx.hasUI) return;

  ctx.ui.notify("メッセージ履歴を読み込んでいます...", "info");
  const messages = await collectHistoryMessages(ctx);
  if (messages.length === 0) {
    ctx.ui.notify("過去のユーザーメッセージが見つかりませんでした", "warning");
    return;
  }

  const selected = await ctx.ui.custom<string | null>(
    (tui, theme, keybindings, done) => {
      return new MessageHistoryPicker(
        messages,
        ctx.cwd,
        ctx.sessionManager.getSessionFile(),
        theme,
        keybindings,
        done,
        () => tui.requestRender(),
      );
    },
    {
      overlay: true,
      overlayOptions: { width: "90%", maxHeight: "80%", anchor: "center" },
    },
  );

  if (selected !== null) {
    const current = ctx.ui.getEditorText().trim();
    if (current.length > 0 && current !== selected.trim()) {
      const replace = await ctx.ui.confirm(
        "エディタのテキストを置き換えますか？",
        "エディタには既にテキストがあります。選択した履歴で置き換えますか？",
      );
      if (!replace) return;
    }
    ctx.ui.setEditorText(selected);
  }
}

export default function messageHistoryExtension(pi: ExtensionAPI) {
  pi.registerShortcut("ctrl+r", {
    description: "Fuzzy-find previous user messages",
    handler: openMessageHistory,
  });
}
