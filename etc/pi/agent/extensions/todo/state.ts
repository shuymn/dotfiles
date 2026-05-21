export const TODO_STATUSES = [
  "pending",
  "in_progress",
  "completed",
  "cancelled",
] as const;

export type TodoStatus = (typeof TODO_STATUSES)[number];

export type TodoItem = {
  id: number;
  title: string;
  description?: string;
  status: TodoStatus;
  activeForm?: string;
  createdAt: number;
  updatedAt: number;
};

export type TodoState = {
  items: TodoItem[];
  nextId: number;
};

export const EMPTY_TODO_STATE: TodoState = { items: [], nextId: 1 };

export const TODO_ACTIONS = ["create", "update", "list", "clear"] as const;

export type TodoAction = (typeof TODO_ACTIONS)[number];

export type TodoCreateItemParams = {
  title: string;
  description?: string;
  activeForm?: string;
};

export type TodoParams =
  | {
      action: "create";
      items: [TodoCreateItemParams, ...TodoCreateItemParams[]];
    }
  | {
      action: "update";
      id?: number;
      title?: string;
      description?: string;
      status?: TodoStatus;
      activeForm?: string;
    }
  | { action: "list" }
  | { action: "clear" };

export type TodoOperation =
  | { kind: "create"; ids: number[] }
  | {
      kind: "update";
      id: number;
      title: string;
      fromStatus: TodoStatus;
      toStatus: TodoStatus;
      autoCleared?: { count: number };
    }
  | { kind: "list" }
  | { kind: "clear"; count: number }
  | { kind: "error"; message: string };

export type TodoToolDetails = {
  action: TodoAction;
  params: Record<string, unknown>;
  state: TodoState;
  op: TodoOperation;
};

export type ApplyResult = {
  state: TodoState;
  op: TodoOperation;
};

export function cloneTodoState(state: TodoState): TodoState {
  return {
    nextId: state.nextId,
    items: state.items.map((item) => ({ ...item })),
  };
}

export function isTodoStatus(value: unknown): value is TodoStatus {
  return (
    typeof value === "string" && TODO_STATUSES.includes(value as TodoStatus)
  );
}

export function isActiveTodoStatus(status: TodoStatus): boolean {
  return status === "pending" || status === "in_progress";
}

export function isTerminalTodoStatus(status: TodoStatus): boolean {
  return status === "completed" || status === "cancelled";
}

function isTodoItem(value: unknown): value is TodoItem {
  if (typeof value !== "object" || value === null) return false;
  const item = value as TodoItem;
  return (
    Number.isInteger(item.id) &&
    item.id > 0 &&
    typeof item.title === "string" &&
    item.title.trim().length > 0 &&
    isTodoStatus(item.status) &&
    typeof item.createdAt === "number" &&
    typeof item.updatedAt === "number" &&
    (item.description === undefined || typeof item.description === "string") &&
    (item.activeForm === undefined || typeof item.activeForm === "string")
  );
}

export function isTodoState(value: unknown): value is TodoState {
  if (typeof value !== "object" || value === null) return false;
  const state = value as TodoState;
  if (!Number.isInteger(state.nextId) || state.nextId < 1) return false;
  if (!Array.isArray(state.items) || !state.items.every(isTodoItem)) {
    return false;
  }
  const ids = new Set<number>();
  let maxId = 0;
  for (const item of state.items) {
    if (ids.has(item.id)) return false;
    ids.add(item.id);
    maxId = Math.max(maxId, item.id);
  }
  if (state.nextId <= maxId) return false;
  return (
    state.items.filter((item) => item.status === "in_progress").length <= 1
  );
}

export function applyTodoMutation(
  state: TodoState,
  params: TodoParams,
  now: number,
): ApplyResult {
  const current = cloneTodoState(state);

  if (params.action === "list") {
    return { state: current, op: { kind: "list" } };
  }

  if (params.action === "clear") {
    return {
      state: cloneTodoState(EMPTY_TODO_STATE),
      op: { kind: "clear", count: current.items.length },
    };
  }

  if (params.action === "create") {
    if (!Array.isArray(params.items) || params.items.length === 0) {
      return {
        state: current,
        op: { kind: "error", message: "items is required for create." },
      };
    }

    const items: TodoItem[] = [];
    for (const [index, candidate] of params.items.entries()) {
      if (typeof candidate !== "object" || candidate === null) {
        return {
          state: current,
          op: {
            kind: "error",
            message: `items[${index}] must be an object for create.`,
          },
        };
      }
      if (typeof candidate.title !== "string") {
        return {
          state: current,
          op: {
            kind: "error",
            message: `items[${index}].title is required for create.`,
          },
        };
      }
      const title = candidate.title.trim();
      if (!title) {
        return {
          state: current,
          op: {
            kind: "error",
            message: `items[${index}].title is required for create.`,
          },
        };
      }
      if (
        candidate.description !== undefined &&
        typeof candidate.description !== "string"
      ) {
        return {
          state: current,
          op: {
            kind: "error",
            message: `items[${index}].description must be a string.`,
          },
        };
      }
      if (
        candidate.activeForm !== undefined &&
        typeof candidate.activeForm !== "string"
      ) {
        return {
          state: current,
          op: {
            kind: "error",
            message: `items[${index}].activeForm must be a string.`,
          },
        };
      }
      items.push({
        id: current.nextId + index,
        title,
        description: candidate.description?.trim() || undefined,
        status: "pending",
        activeForm: candidate.activeForm?.trim() || undefined,
        createdAt: now,
        updatedAt: now,
      });
    }

    return {
      state: {
        items: [...current.items, ...items],
        nextId: current.nextId + items.length,
      },
      op: { kind: "create", ids: items.map((item) => item.id) },
    };
  }

  if (params.action === "update") {
    if (!Number.isInteger(params.id)) {
      return {
        state: current,
        op: { kind: "error", message: "id is required for update." },
      };
    }
    const id = params.id as number;
    const hasMutation =
      params.status !== undefined ||
      params.title !== undefined ||
      params.description !== undefined ||
      params.activeForm !== undefined;
    if (!hasMutation) {
      return {
        state: current,
        op: {
          kind: "error",
          message: "update requires status, title, description, or activeForm.",
        },
      };
    }
    if (params.status !== undefined && !isTodoStatus(params.status)) {
      return {
        state: current,
        op: { kind: "error", message: "status is invalid." },
      };
    }

    const existing = current.items.find((item) => item.id === id);
    if (!existing) {
      return {
        state: current,
        op: { kind: "error", message: `unknown todo id: ${id}.` },
      };
    }

    const fromStatus = existing.status;
    const toStatus = params.status ?? existing.status;
    const title = params.title?.trim();
    if (params.title !== undefined && !title) {
      return {
        state: current,
        op: { kind: "error", message: "title must not be empty." },
      };
    }

    const items = current.items.map((item) => {
      if (
        params.status === "in_progress" &&
        item.id !== id &&
        item.status === "in_progress"
      ) {
        return { ...item, status: "pending" as const, updatedAt: now };
      }
      if (item.id !== id) return item;
      return {
        ...item,
        title: title ?? item.title,
        description:
          params.description === undefined
            ? item.description
            : params.description.trim() || undefined,
        activeForm:
          params.activeForm === undefined
            ? item.activeForm
            : params.activeForm.trim() || undefined,
        status: toStatus,
        updatedAt: now,
      };
    });

    const nextState = { items, nextId: current.nextId };
    const op: TodoOperation = {
      kind: "update",
      id,
      title: title ?? existing.title,
      fromStatus,
      toStatus,
    };
    const hasActiveTodos = items.some((item) =>
      isActiveTodoStatus(item.status),
    );
    const closedActiveTodo =
      isActiveTodoStatus(fromStatus) && isTerminalTodoStatus(toStatus);
    if (closedActiveTodo && !hasActiveTodos) {
      return {
        state: cloneTodoState(EMPTY_TODO_STATE),
        op: { ...op, autoCleared: { count: items.length } },
      };
    }

    return { state: nextState, op };
  }

  return { state: current, op: { kind: "error", message: "unknown action." } };
}
