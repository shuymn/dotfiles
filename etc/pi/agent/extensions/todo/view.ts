import { truncateToWidth } from "@earendil-works/pi-tui";
import { activeTodos, completedCount, orderedTodos } from "./selectors";
import type { TodoItem, TodoState } from "./state";

export type WidgetLine = { text: string; color?: string; dim?: boolean };

export function statusIcon(status: TodoItem["status"]): string {
  switch (status) {
    case "pending":
      return "○";
    case "in_progress":
      return "◐";
    case "completed":
      return "✓";
    case "cancelled":
      return "×";
  }
}

function colorFor(
  status: TodoItem["status"],
): Pick<WidgetLine, "color" | "dim"> {
  switch (status) {
    case "in_progress":
      return { color: "accent" };
    case "completed":
      return { color: "success", dim: true };
    case "cancelled":
      return { color: "warning", dim: true };
    case "pending":
      return {};
  }
}

export function renderWidgetLines(
  state: TodoState,
  options: { width?: number; maxLines?: number } = {},
): WidgetLine[] | undefined {
  if (activeTodos(state).length === 0) return undefined;

  const width = options.width ?? 80;
  const maxLines = options.maxLines ?? 12;
  const done = completedCount(state);
  const headerColor = state.items.some((item) => item.status === "in_progress")
    ? "accent"
    : "dim";
  const lines: WidgetLine[] = [
    { text: `● Todos ${done}/${state.items.length}`, color: headerColor },
  ];
  const items = orderedTodos(state);
  const capacity = Math.max(0, maxLines - 1);
  const shown = items.slice(0, capacity);
  for (const [index, item] of shown.entries()) {
    const branch =
      index === shown.length - 1 && shown.length === items.length ? "└─" : "├─";
    lines.push({
      text: `${branch} ${statusIcon(item.status)} ${item.activeForm ?? item.title}`,
      ...colorFor(item.status),
    });
  }
  const hidden = items.length - shown.length;
  if (hidden > 0) {
    if (lines.length >= maxLines) lines.pop();
    lines.push({ text: `└─ +${hidden} more`, color: "dim", dim: true });
  }

  return lines.map((line) => ({
    ...line,
    text: truncateToWidth(line.text, width, ""),
  }));
}

export function renderWidgetText(
  state: TodoState,
  options: { width?: number; maxLines?: number } = {},
): string[] | undefined {
  return renderWidgetLines(state, options)?.map((line) => line.text);
}
