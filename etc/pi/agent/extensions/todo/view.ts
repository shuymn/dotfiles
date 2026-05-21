import {
  appendOverflowLine,
  treeBranch,
  truncateWidgetLines,
  widgetLinesToText,
  widgetStatusIcon,
  type WidgetLine,
} from "../lib/widget-view";
import { activeTodos, completedCount, orderedTodos } from "./selectors";
import type { TodoItem, TodoState } from "./state";

export type { WidgetLine } from "../lib/widget-view";

export function statusIcon(status: TodoItem["status"]): string {
  return widgetStatusIcon(status === "in_progress" ? "running" : status);
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
  if (maxLines <= 0) return [];

  const done = completedCount(state);
  const headerColor = state.items.some((item) => item.status === "in_progress")
    ? "accent"
    : "dim";
  const lines: WidgetLine[] = [
    { text: `● Todos ${done}/${state.items.length}`, color: headerColor },
  ];

  const items = orderedTodos(state);
  const itemCapacity = Math.max(0, maxLines - 1);
  const shownCount = items.length > itemCapacity ? Math.max(0, itemCapacity - 1) : itemCapacity;
  const shown = items.slice(0, shownCount);
  const hidden = items.length - shown.length;
  const renderedRows = shown.length + (hidden > 0 ? 1 : 0);
  for (const [index, item] of shown.entries()) {
    const branch = treeBranch(index, renderedRows);
    lines.push({
      text: `${branch} ${statusIcon(item.status)} ${item.activeForm ?? item.title}`,
      ...colorFor(item.status),
    });
  }
  appendOverflowLine(lines, hidden, maxLines);

  return truncateWidgetLines(lines, width);
}

export function renderWidgetText(
  state: TodoState,
  options: { width?: number; maxLines?: number } = {},
): string[] | undefined {
  const lines = renderWidgetLines(state, options);
  return lines ? widgetLinesToText(lines) : undefined;
}
