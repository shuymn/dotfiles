import {
  cloneTodoState,
  EMPTY_TODO_STATE,
  isTodoState,
  type TodoState,
} from "./state";

export const TOOL_NAME = "todo";

type EntryLike = {
  type?: unknown;
  message?: {
    role?: unknown;
    toolName?: unknown;
    details?: unknown;
  };
};

type SessionManagerLike = {
  getBranch?: () => unknown[];
  getEntries?: () => unknown[];
};

function extractSnapshot(entry: unknown): TodoState | undefined {
  const candidate = entry as EntryLike;
  if (candidate.type !== "message") return undefined;
  if (candidate.message?.role !== "toolResult") return undefined;
  if (candidate.message.toolName !== TOOL_NAME) return undefined;
  const details = candidate.message.details as { state?: unknown } | undefined;
  if (!isTodoState(details?.state)) return undefined;
  return details.state;
}

export function replayTodoState(sessionManager: SessionManagerLike): TodoState {
  const entries =
    sessionManager.getBranch?.() ?? sessionManager.getEntries?.() ?? [];
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    const snapshot = extractSnapshot(entries[index]);
    if (snapshot) return cloneTodoState(snapshot);
  }
  return cloneTodoState(EMPTY_TODO_STATE);
}
