import { truncateToWidth } from "@earendil-works/pi-tui";

export type WidgetLine = { text: string; color?: string; dim?: boolean };

export type WidgetStatus =
  | "pending"
  | "queued"
  | "running"
  | "completed"
  | "cancelled"
  | "failed";

export function widgetStatusIcon(status: WidgetStatus): string {
  switch (status) {
    case "pending":
    case "queued":
      return "○";
    case "running":
      return "◐";
    case "completed":
      return "✓";
    case "cancelled":
      return "×";
    case "failed":
      return "!";
  }
}

export function treeBranch(
  index: number,
  total: number,
): "├─" | "└─" {
  return index === total - 1 ? "└─" : "├─";
}

export function truncateWidgetLines(
  lines: WidgetLine[],
  width: number,
): WidgetLine[] {
  return lines.map((line) => ({
    ...line,
    text: truncateToWidth(line.text, width, ""),
  }));
}

export function widgetLinesToText(lines: WidgetLine[]): string[] {
  return lines.map((line) => line.text);
}

export function overflowLine(
  hidden: number,
  branch: "├─" | "└─" = "└─",
): WidgetLine {
  return { text: `${branch} +${hidden} more`, color: "dim", dim: true };
}

export function appendOverflowLine(
  lines: WidgetLine[],
  hidden: number,
  maxLines: number,
): void {
  if (hidden <= 0 || maxLines <= 0 || lines.length >= maxLines) return;
  lines.push(overflowLine(hidden));
}
