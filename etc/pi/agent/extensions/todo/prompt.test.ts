import { describe, expect, test } from "bun:test";
import { renderTodoReminder } from "./prompt";
import type { TodoState } from "./state";

const state: TodoState = {
  nextId: 5,
  items: [
    { id: 1, title: "Done", status: "completed", createdAt: 1, updatedAt: 1 },
    {
      id: 2,
      title: "Active",
      status: "in_progress",
      createdAt: 1,
      updatedAt: 1,
    },
    { id: 3, title: "Next", status: "pending", createdAt: 1, updatedAt: 1 },
    { id: 4, title: "Later", status: "pending", createdAt: 1, updatedAt: 1 },
  ],
};

describe("todo prompt", () => {
  test("returns undefined for empty state", () => {
    expect(renderTodoReminder({ items: [], nextId: 1 })).toBeUndefined();
  });

  test("prioritizes in_progress and pending and includes protocol", () => {
    const reminder = renderTodoReminder(state)!;
    expect(reminder).toContain("● #2 Active");
    expect(reminder).toContain("○ #3 Next");
    expect(reminder.indexOf("#2 Active")).toBeLessThan(
      reminder.indexOf("#1 Done"),
    );
    expect(reminder).toContain(
      "- Before final response, close or explicitly explain remaining todos.",
    );
  });

  test("collapses overflow", () => {
    const reminder = renderTodoReminder(state, { maxLines: 9 })!;
    expect(reminder).toContain("... ");
    expect(reminder.split("\n").length).toBeLessThanOrEqual(9);
  });
});
