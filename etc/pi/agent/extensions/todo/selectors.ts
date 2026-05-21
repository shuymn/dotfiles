import type { TodoItem, TodoState } from "./state";
import { isActiveTodoStatus } from "./state";

const ACTIVE_ORDER: Record<TodoItem["status"], number> = {
  in_progress: 0,
  pending: 1,
  completed: 2,
  cancelled: 3,
};

export function activeTodos(state: TodoState): TodoItem[] {
  return state.items.filter((item) => isActiveTodoStatus(item.status));
}

export function inProgressTodo(state: TodoState): TodoItem | undefined {
  return state.items.find((item) => item.status === "in_progress");
}

export function pendingTodos(state: TodoState): TodoItem[] {
  return state.items.filter((item) => item.status === "pending");
}

export function completedCount(state: TodoState): number {
  return state.items.filter((item) => item.status === "completed").length;
}

export function orderedTodos(state: TodoState): TodoItem[] {
  return [...state.items].sort((left, right) => {
    const byStatus = ACTIVE_ORDER[left.status] - ACTIVE_ORDER[right.status];
    return byStatus || left.id - right.id;
  });
}
