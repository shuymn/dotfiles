import { describe, expect, test } from "bun:test";
import type { TodoCreateItemParams } from "./state";
import { applyTodoMutation, EMPTY_TODO_STATE } from "./state";

const NOW = 1000;

const createItems = <
  T extends [TodoCreateItemParams, ...TodoCreateItemParams[]],
>(
  items: T,
) => ({
  action: "create" as const,
  items,
});

const createOne = (title: string) => createItems([{ title }]);

describe("todo state", () => {
  test("create adds consecutive pending todos", () => {
    const result = applyTodoMutation(
      EMPTY_TODO_STATE,
      createItems([
        { title: "Investigate widget", description: "Find current shape" },
        { title: "Implement widget", activeForm: "Implementing widget" },
      ]),
      NOW,
    );
    expect(result.op).toEqual({ kind: "create", ids: [1, 2] });
    expect(result.state).toEqual({
      nextId: 3,
      items: [
        {
          id: 1,
          title: "Investigate widget",
          description: "Find current shape",
          status: "pending",
          createdAt: NOW,
          updatedAt: NOW,
        },
        {
          id: 2,
          title: "Implement widget",
          activeForm: "Implementing widget",
          status: "pending",
          createdAt: NOW,
          updatedAt: NOW,
        },
      ],
    });
  });

  test("create without items returns an error op without mutation", () => {
    const result = applyTodoMutation(
      EMPTY_TODO_STATE,
      { action: "create" } as never,
      NOW,
    );
    expect(result.op).toEqual({
      kind: "error",
      message: "items is required for create.",
    });
    expect(result.state).toEqual(EMPTY_TODO_STATE);
  });

  test("create with invalid items returns an error op without mutation", () => {
    const cases = [
      {
        params: { action: "create", items: [{ title: "A" }, { title: "  " }] },
        message: "items[1].title is required for create.",
      },
      {
        params: { action: "create", items: [null] },
        message: "items[0] must be an object for create.",
      },
      {
        params: { action: "create", items: [{ title: 123 }] },
        message: "items[0].title is required for create.",
      },
      {
        params: { action: "create", items: [{ title: "A", description: 123 }] },
        message: "items[0].description must be a string.",
      },
      {
        params: { action: "create", items: [{ title: "A", activeForm: 123 }] },
        message: "items[0].activeForm must be a string.",
      },
      {
        params: { action: "create", title: "A" },
        message: "items is required for create.",
      },
    ];

    for (const { params, message } of cases) {
      const result = applyTodoMutation(EMPTY_TODO_STATE, params as never, NOW);
      expect(result.op).toEqual({ kind: "error", message });
      expect(result.state).toEqual(EMPTY_TODO_STATE);
    }
  });

  test("update changes status and rejects unknown ids", () => {
    const first = applyTodoMutation(
      EMPTY_TODO_STATE,
      createOne("A"),
      NOW,
    ).state;
    const created = applyTodoMutation(first, createOne("B"), NOW).state;
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
    const one = applyTodoMutation(EMPTY_TODO_STATE, createOne("A"), NOW).state;
    const two = applyTodoMutation(one, createOne("B"), NOW).state;
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
      createOne("A"),
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
      createOne("A"),
      NOW,
    ).state;
    const cleared = applyTodoMutation(created, { action: "clear" }, NOW);
    expect(cleared.op).toEqual({ kind: "clear", count: 1 });
    expect(cleared.state).toEqual(EMPTY_TODO_STATE);
  });
});
