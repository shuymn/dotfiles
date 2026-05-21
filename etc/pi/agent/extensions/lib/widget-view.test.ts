import { describe, expect, test } from "bun:test";
import { stripVTControlCharacters } from "node:util";
import {
  appendOverflowLine,
  treeBranch,
  truncateWidgetLines,
  widgetLinesToText,
  widgetStatusIcon,
  type WidgetLine,
} from "./widget-view";

describe("widget-view helpers", () => {
  test("maps shared widget statuses to icons", () => {
    expect(widgetStatusIcon("pending")).toBe("○");
    expect(widgetStatusIcon("queued")).toBe("○");
    expect(widgetStatusIcon("running")).toBe("◐");
    expect(widgetStatusIcon("completed")).toBe("✓");
    expect(widgetStatusIcon("cancelled")).toBe("×");
    expect(widgetStatusIcon("failed")).toBe("!");
  });

  test("renders tree branches", () => {
    expect(treeBranch(0, 2)).toBe("├─");
    expect(treeBranch(1, 2)).toBe("└─");
  });

  test("truncates and converts widget lines without dropping metadata", () => {
    const lines: WidgetLine[] = [{ text: "abcdef", color: "accent" }];

    const truncated = truncateWidgetLines(lines, 4);

    expect(stripVTControlCharacters(truncated[0].text)).toBe("abcd");
    expect(truncated[0].color).toBe("accent");
    expect(widgetLinesToText(truncated).map(stripVTControlCharacters)).toEqual([
      "abcd",
    ]);
  });

  test("appends overflow line only when capacity remains", () => {
    const lines: WidgetLine[] = [{ text: "header" }, { text: "item 1" }];

    appendOverflowLine(lines, 3, 3);

    expect(lines).toEqual([
      { text: "header" },
      { text: "item 1" },
      { text: "└─ +3 more", color: "dim", dim: true },
    ]);

    appendOverflowLine(lines, 1, 3);
    expect(lines).toHaveLength(3);
  });

  test("does not append overflow when max lines is zero", () => {
    const lines: WidgetLine[] = [{ text: "header" }];

    appendOverflowLine(lines, 3, 0);

    expect(lines).toEqual([{ text: "header" }]);
  });
});
