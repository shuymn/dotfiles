import { describe, expect, test } from "bun:test";
import { applyTodoMutation, EMPTY_TODO_STATE } from "./state";

const NOW = 1000;

describe("todo state", () => {
  test("create adds a pending todo", () => {
    const result = applyTodoMutation(
      EMPTY_TODO_STATE,
      { action: "create", title: "Implement widget" },
      NOW,
    );
    expect(result.op).toEqual({ kind: "create", id: 1 });
    expect(result.state).toEqual({
      nextId: 2,
      items: [
        {
          id: 1,
          title: "Implement widget",
          status: "pending",
          createdAt: NOW,
          updatedAt: NOW,
        },
      ],
    });
  });

  test("create without title returns an error op without mutation", () => {
    const result = applyTodoMutation(
      EMPTY_TODO_STATE,
      { action: "create" },
      NOW,
    );
    expect(result.op.kind).toBe("error");
    expect(result.state).toEqual(EMPTY_TODO_STATE);
  });

  test("update changes status and rejects unknown ids", () => {
    const first = applyTodoMutation(
      EMPTY_TODO_STATE,
      { action: "create", title: "A" },
      NOW,
    ).state;
    const created = applyTodoMutation(
      first,
      { action: "create", title: "B" },
      NOW,
    ).state;
    const updated = applyTodoMutation(
      created,
      { action: "update", id: 1, status: "completed" },
      NOW + 1,
    );
    expect(updated.op).toEqual({
      kind: "update",
      id: 1,
      title: "A",
      fromStatus: "pending",
      toStatus: "completed",
    });
    expect(updated.state.items[0].status).toBe("completed");

    const missing = applyTodoMutation(
      created,
      { action: "update", id: 99, status: "completed" },
      NOW + 1,
    );
    expect(missing.op).toEqual({
      kind: "error",
      message: "unknown todo id: 99.",
    });
  });

  test("setting in_progress returns any previous in_progress item to pending", () => {
    const one = applyTodoMutation(
      EMPTY_TODO_STATE,
      { action: "create", title: "A" },
      NOW,
    ).state;
    const two = applyTodoMutation(
      one,
      { action: "create", title: "B" },
      NOW,
    ).state;
    const activeA = applyTodoMutation(
      two,
      { action: "update", id: 1, status: "in_progress" },
      NOW,
    ).state;
    const activeB = applyTodoMutation(
      activeA,
      { action: "update", id: 2, status: "in_progress" },
      NOW,
    ).state;
    expect(activeB.items.map((item) => [item.id, item.status])).toEqual([
      [1, "pending"],
      [2, "in_progress"],
    ]);
  });

  test("updating the final active todo to terminal status auto-clears closed todos", () => {
    const created = applyTodoMutation(
      EMPTY_TODO_STATE,
      { action: "create", title: "A" },
      NOW,
    ).state;
    const completed = applyTodoMutation(
      created,
      { action: "update", id: 1, status: "completed" },
      NOW + 1,
    );

    expect(completed.op).toEqual({
      kind: "update",
      id: 1,
      title: "A",
      fromStatus: "pending",
      toStatus: "completed",
      autoCleared: { count: 1 },
    });
    expect(completed.state).toEqual(EMPTY_TODO_STATE);

    const cancelled = applyTodoMutation(
      created,
      { action: "update", id: 1, status: "cancelled" },
      NOW + 1,
    );
    expect(cancelled.op).toEqual({
      kind: "update",
      id: 1,
      title: "A",
      fromStatus: "pending",
      toStatus: "cancelled",
      autoCleared: { count: 1 },
    });
    expect(cancelled.state).toEqual(EMPTY_TODO_STATE);
  });

  test("metadata-only updates to terminal-only todos do not auto-clear", () => {
    const state = {
      nextId: 2,
      items: [
        {
          id: 1,
          title: "A",
          status: "completed" as const,
          createdAt: NOW,
          updatedAt: NOW,
        },
      ],
    };

    const updated = applyTodoMutation(
      state,
      { action: "update", id: 1, description: "Done" },
      NOW + 1,
    );

    expect(updated.op).toEqual({
      kind: "update",
      id: 1,
      title: "A",
      fromStatus: "completed",
      toStatus: "completed",
    });
    expect(updated.state.items).toEqual([
      {
        id: 1,
        title: "A",
        description: "Done",
        status: "completed",
        createdAt: NOW,
        updatedAt: NOW + 1,
      },
    ]);
  });

  test("clear resets items and nextId", () => {
    const created = applyTodoMutation(
      EMPTY_TODO_STATE,
      { action: "create", title: "A" },
      NOW,
    ).state;
    const cleared = applyTodoMutation(created, { action: "clear" }, NOW);
    expect(cleared.op).toEqual({ kind: "clear", count: 1 });
    expect(cleared.state).toEqual(EMPTY_TODO_STATE);
  });
});
