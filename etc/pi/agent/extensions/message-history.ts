import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { DynamicBorder, SessionManager } from "@earendil-works/pi-coding-agent";
import {
    Input,
    Key,
    fuzzyFilter,
    matchesKey,
    truncateToWidth,
    type Component,
    type Focusable,
} from "@earendil-works/pi-tui";

const MAX_SESSIONS_TO_SCAN = 200;
const MAX_MESSAGES_TO_SHOW = 1000;
const MAX_MESSAGE_CHARS = 4000;

type HistoryMessage = {
    text: string;
    timestamp: number;
    cwd?: string;
    sessionName?: string;
    sessionPath?: string;
};

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

function displaySnippet(text: string): string {
    const oneLine = text.replace(/\s+/g, " ").trim();
    return oneLine.length > 180 ? `${oneLine.slice(0, 177)}...` : oneLine;
}

function formatDescription(item: HistoryMessage): string {
    const date = new Date(item.timestamp || Date.now());
    const when = Number.isNaN(date.getTime()) ? "unknown time" : date.toLocaleString();
    const source = item.sessionName || item.cwd || item.sessionPath || "current session";
    return `${when} · ${source}`;
}

function collectFromEntries(
    entries: ReturnType<ExtensionContext["sessionManager"]["getEntries"]>,
    meta: Pick<HistoryMessage, "cwd" | "sessionName" | "sessionPath"> = {},
): HistoryMessage[] {
    const messages: HistoryMessage[] = [];
    for (const entry of entries) {
        if (entry.type !== "message") continue;
        const text = userMessageText(entry.message);
        if (!text) continue;

        messages.push({
            text: text.length > MAX_MESSAGE_CHARS ? `${text.slice(0, MAX_MESSAGE_CHARS)}\n...[truncated]` : text,
            timestamp: Number((entry.message as { timestamp?: number }).timestamp) || Date.parse(entry.timestamp),
            ...meta,
        });
    }
    return messages;
}

async function collectHistoryMessages(ctx: ExtensionContext): Promise<HistoryMessage[]> {
    const byText = new Map<string, HistoryMessage>();

    const add = (items: HistoryMessage[]) => {
        for (const item of items) {
            const key = item.text.trim();
            if (!key) continue;
            const existing = byText.get(key);
            if (!existing || item.timestamp > existing.timestamp) byText.set(key, item);
        }
    };

    add(
        collectFromEntries(ctx.sessionManager.getEntries(), {
            cwd: ctx.cwd,
            sessionName: ctx.sessionManager.getSessionName(),
            sessionPath: ctx.sessionManager.getSessionFile(),
        }),
    );

    try {
        const sessions = (await SessionManager.listAll()).sort((a, b) => b.modified.getTime() - a.modified.getTime());
        for (const session of sessions.slice(0, MAX_SESSIONS_TO_SCAN)) {
            if (session.path === ctx.sessionManager.getSessionFile()) continue;
            try {
                const sm = SessionManager.open(session.path);
                add(
                    collectFromEntries(sm.getEntries(), {
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

    return [...byText.values()].sort((a, b) => b.timestamp - a.timestamp).slice(0, MAX_MESSAGES_TO_SHOW);
}

class MessageHistoryPicker implements Component, Focusable {
    private input = new Input();
    private selectedIndex = 0;
    private filtered: HistoryMessage[];
    private focusedValue = false;

    constructor(
        private readonly items: HistoryMessage[],
        private readonly theme: {
            fg(color: string, text: string): string;
            bold(text: string): string;
        },
        private readonly keybindings: { matches(data: string, id: string): boolean },
        private readonly done: (value: string | null) => void,
        private readonly requestRender: () => void,
    ) {
        this.filtered = items;
    }

    get focused(): boolean {
        return this.focusedValue;
    }

    set focused(value: boolean) {
        this.focusedValue = value;
        this.input.focused = value;
    }

    invalidate(): void {
        this.input.invalidate();
    }

    render(width: number): string[] {
        const lines: string[] = [];
        lines.push(...new DynamicBorder((s: string) => this.theme.fg("accent", s)).render(width));
        lines.push(truncateToWidth(this.theme.fg("accent", this.theme.bold("Search previous user messages")), width));
        lines.push(...this.input.render(width));
        lines.push("");

        if (this.filtered.length === 0) {
            lines.push(this.theme.fg("warning", "  No matching messages"));
        } else {
            const maxVisible = Math.max(1, Math.min(12, this.filtered.length));
            const start = Math.max(
                0,
                Math.min(this.selectedIndex - Math.floor(maxVisible / 2), this.filtered.length - maxVisible),
            );
            const end = Math.min(start + maxVisible, this.filtered.length);

            for (let i = start; i < end; i++) {
                const item = this.filtered[i]!;
                const selected = i === this.selectedIndex;
                const prefix = selected ? "→ " : "  ";
                const snippet = displaySnippet(item.text);
                const line = prefix + snippet;
                lines.push(
                    selected ? truncateToWidth(this.theme.fg("accent", line), width) : truncateToWidth(line, width),
                );

                if (selected) {
                    lines.push(truncateToWidth(this.theme.fg("dim", `    ${formatDescription(item)}`), width));
                }
            }

            if (start > 0 || end < this.filtered.length) {
                lines.push(
                    this.theme.fg(
                        "dim",
                        truncateToWidth(`  (${this.selectedIndex + 1}/${this.filtered.length})`, width),
                    ),
                );
            }
        }

        lines.push("");
        lines.push(this.theme.fg("dim", "  Type to fuzzy-search · ↑↓/Ctrl-JK navigate · Enter insert · Esc cancel"));
        lines.push(...new DynamicBorder((s: string) => this.theme.fg("accent", s)).render(width));
        return lines.map((line) => truncateToWidth(line, width));
    }

    handleInput(data: string): void {
        if (this.keybindings.matches(data, "tui.select.up") || matchesKey(data, Key.ctrl("k"))) {
            if (this.filtered.length > 0) {
                this.selectedIndex = this.selectedIndex === 0 ? this.filtered.length - 1 : this.selectedIndex - 1;
            }
            this.requestRender();
            return;
        }

        if (this.keybindings.matches(data, "tui.select.down") || matchesKey(data, Key.ctrl("j"))) {
            if (this.filtered.length > 0) {
                this.selectedIndex = this.selectedIndex === this.filtered.length - 1 ? 0 : this.selectedIndex + 1;
            }
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

    private applyFilter(): void {
        const query = this.input.getValue().trim();
        this.filtered = query.length === 0 ? this.items : fuzzyFilter(this.items, query, (item) => item.text);
        this.selectedIndex = 0;
    }
}

async function openMessageHistory(ctx: ExtensionContext): Promise<void> {
    if (!ctx.hasUI) return;

    ctx.ui.notify("Loading message history...", "info");
    const messages = await collectHistoryMessages(ctx);
    if (messages.length === 0) {
        ctx.ui.notify("No previous user messages found", "warning");
        return;
    }

    const selected = await ctx.ui.custom<string | null>(
        (tui, theme, keybindings, done) => {
            return new MessageHistoryPicker(messages, theme, keybindings, done, () => tui.requestRender());
        },
        { overlay: true, overlayOptions: { width: "90%", maxHeight: "80%", anchor: "center" } },
    );

    if (selected !== null) {
        const current = ctx.ui.getEditorText().trim();
        if (current.length > 0 && current !== selected.trim()) {
            const replace = await ctx.ui.confirm(
                "Replace editor text?",
                "The editor already contains text. Replace it with the selected history entry?",
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
