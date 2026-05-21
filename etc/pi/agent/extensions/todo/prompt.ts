import { activeTodos, inProgressTodo, pendingTodos } from "./selectors";
import { isTerminalTodoStatus, type TodoItem, type TodoState } from "./state";

const DEFAULT_MAX_LINES = 12;

function icon(item: TodoItem): string {
  switch (item.status) {
    case "in_progress":
      return "●";
    case "pending":
      return "○";
    case "completed":
      return "✓";
    case "cancelled":
      return "×";
  }
}

export function renderTodoReminder(
  state: TodoState,
  options: { maxLines?: number } = {},
): string | undefined {
  if (state.items.length === 0) return undefined;

  const maxLines = options.maxLines ?? DEFAULT_MAX_LINES;
  const candidates = [
    ...activeTodos(state),
    ...state.items.filter((item) => isTerminalTodoStatus(item.status)),
  ];
  const protocol = [
    "Protocol:",
    "- Continue the single in_progress todo.",
    "- If no todo is in_progress, pick the next pending todo before tool use.",
    "- Before final response, close or explicitly explain remaining todos.",
  ];
  const header = ["<todo-state>", "Current todos:"];
  const footer = ["</todo-state>"];
  const fixedLineCount = header.length + 1 + protocol.length + footer.length;
  const rawTodoCapacity = Math.max(0, maxLines - fixedLineCount);
  const needsOverflow = candidates.length > rawTodoCapacity;
  const todoCapacity = needsOverflow
    ? Math.max(0, rawTodoCapacity - 1)
    : rawTodoCapacity;
  const shown = candidates.slice(0, todoCapacity);
  const hidden = Math.max(0, candidates.length - shown.length);
  const todoLines = shown.map(
    (item) => `${icon(item)} #${item.id} ${item.title}`,
  );
  if (hidden > 0) todoLines.push(`... ${hidden} more`);

  return [...header, ...todoLines, "", ...protocol, ...footer].join("\n");
}

export function nextActionText(state: TodoState): string | undefined {
  const active = inProgressTodo(state);
  const pending = pendingTodos(state);
  if (!active && pending.length > 0) {
    return "No todo is in_progress. Pick one pending todo and mark it in_progress before continuing.";
  }
  return undefined;
}
