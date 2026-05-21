import { describe, expect, test } from "bun:test";
import type { TodoItem, TodoState } from "./state";
import { renderWidgetLines, renderWidgetText, statusIcon } from "./view";

function terminalState(statuses: Array<TodoItem["status"]>): TodoState {
  return {
    nextId: statuses.length + 1,
    items: statuses.map((status, index) => ({
      id: index + 1,
      title: status,
      status,
      createdAt: 1,
      updatedAt: 1,
    })),
  };
}

const state: TodoState = {
  nextId: 5,
  items: [
    {
      id: 1,
      title: "Pending item with a very long title",
      status: "pending",
      createdAt: 1,
      updatedAt: 1,
    },
    {
      id: 2,
      title: "Active item",
      activeForm: "Doing now",
      status: "in_progress",
      createdAt: 1,
      updatedAt: 1,
    },
    {
      id: 3,
      title: "Done item",
      status: "completed",
      createdAt: 1,
      updatedAt: 1,
    },
    {
      id: 4,
      title: "Cancelled item",
      status: "cancelled",
      createdAt: 1,
      updatedAt: 1,
    },
  ],
};

describe("todo widget", () => {
  test("returns undefined for empty state", () => {
    expect(renderWidgetText({ items: [], nextId: 1 })).toBeUndefined();
  });

  test("returns undefined when only terminal todos remain", () => {
    const terminalCases = [
      terminalState(["completed"]),
      terminalState(["cancelled"]),
      terminalState(["completed", "cancelled"]),
    ];

    for (const state of terminalCases) {
      expect(renderWidgetText(state)).toBeUndefined();
      expect(renderWidgetLines(state)).toBeUndefined();
    }
  });

  test("has icons and color policy for every status", () => {
    expect(statusIcon("pending")).toBe("○");
    expect(statusIcon("in_progress")).toBe("◐");
    expect(statusIcon("completed")).toBe("✓");
    expect(statusIcon("cancelled")).toBe("×");
    const lines = renderWidgetLines(state)!;
    expect(
      lines.some(
        (line) => line.text.includes("◐ Doing now") && line.color === "accent",
      ),
    ).toBe(true);
    expect(
      lines.some((line) => line.text.includes("✓ Done item") && line.dim),
    ).toBe(true);
  });

  test("truncates to width and shows overflow", () => {
    const lines = renderWidgetText(state, { width: 16, maxLines: 3 })!;
    expect(lines.every((line) => line.length <= 16)).toBe(true);
    expect(lines.at(-1)).toContain("more");
  });
});
