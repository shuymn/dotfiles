import {
  overflowLine,
  treeBranch,
  truncateWidgetLines,
  type WidgetLine,
  widgetLinesToText,
  widgetStatusIcon,
} from "../lib/widget-view";
import type { ActiveReviewRun } from "./workflow";

export type ReviewPhaseWidgetState = "queued" | "running";

export function phaseLabel(file: string): string {
  const match = file.match(/^\d+-(.+)\.md$/);
  if (!match) return file;
  return match[1]
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

type ReviewTimelineRow = {
  phaseFile: string;
  status: "completed" | ReviewPhaseWidgetState;
  occurrence: number;
};

function buildTimeline(
  run: ActiveReviewRun,
  phaseIndex: number,
  state: ReviewPhaseWidgetState,
): ReviewTimelineRow[] {
  const occurrences = new Map<string, number>();
  const completedRows =
    run.phaseOutputs.length > 0
      ? run.phaseOutputs.map((output) => output.phaseFile)
      : run.phases.slice(0, phaseIndex).map((phase) => phase.file);
  const rows: ReviewTimelineRow[] = completedRows.map((phaseFile) => {
    const occurrence = (occurrences.get(phaseFile) ?? 0) + 1;
    occurrences.set(phaseFile, occurrence);
    return {
      phaseFile,
      status: "completed",
      occurrence,
    };
  });

  const currentPhaseFile = run.phases[phaseIndex]?.file;
  if (currentPhaseFile) {
    const occurrence = (occurrences.get(currentPhaseFile) ?? 0) + 1;
    rows.push({ phaseFile: currentPhaseFile, status: state, occurrence });
  }

  return rows;
}

function timelineLabel(row: ReviewTimelineRow): string {
  const suffix = row.occurrence > 1 ? ` #${row.occurrence}` : "";
  return `${phaseLabel(row.phaseFile)}${suffix}`;
}

function renderTimelineRow(
  row: ReviewTimelineRow,
  branch: "├─" | "└─",
  state: ReviewPhaseWidgetState,
  extraSuffix = "",
): WidgetLine {
  const isCurrentPhase = row.status !== "completed";
  const stateSuffix = isCurrentPhase ? ` ${state}` : "";
  return {
    text: `${branch} ${widgetStatusIcon(row.status)} ${timelineLabel(row)}${stateSuffix}${extraSuffix}`,
    color: isCurrentPhase
      ? state === "running"
        ? "accent"
        : "dim"
      : "success",
    dim: !isCurrentPhase,
  };
}

export function renderReviewWidgetLines(
  run: ActiveReviewRun,
  state: ReviewPhaseWidgetState,
  phaseNumber: number,
  options: { width?: number; maxLines?: number } = {},
): WidgetLine[] {
  const width = options.width ?? 80;
  const maxLines = options.maxLines ?? 12;
  if (maxLines <= 0) return [];

  const phaseIndex = Math.min(
    Math.max(phaseNumber - 1, 0),
    run.phases.length - 1,
  );
  const phaseCount = run.phases.length;
  const timeline = buildTimeline(run, phaseIndex, state);
  const stepNumber = timeline.length || phaseNumber;
  const isLooping = stepNumber > phaseNumber;
  const headerColor = state === "running" ? "accent" : "dim";
  const lines: WidgetLine[] = [
    {
      text: isLooping
        ? `● Review step ${stepNumber} ${state}`
        : `● Review ${phaseNumber}/${phaseCount} ${state}`,
      color: headerColor,
    },
  ];
  if (maxLines === 1 || phaseCount === 0)
    return truncateWidgetLines(lines, width);

  const rowCapacity = maxLines - 1;
  const hasOverflow = timeline.length > rowCapacity;
  const shownCount = hasOverflow ? Math.max(1, rowCapacity - 1) : rowCapacity;
  const startIndex = Math.max(0, timeline.length - shownCount);
  const shownRows = timeline.slice(startIndex);
  const hidden = startIndex;

  if (hidden > 0 && rowCapacity === 1) {
    const row = shownRows.at(-1);
    if (row)
      lines.push(
        renderTimelineRow(row, treeBranch(0, 1), state, ` (+${hidden} more)`),
      );
    return truncateWidgetLines(lines, width);
  }

  const renderedRows = shownRows.length + (hidden > 0 ? 1 : 0);
  let rowIndex = 0;
  if (hidden > 0)
    lines.push(overflowLine(hidden, treeBranch(rowIndex++, renderedRows)));

  for (const row of shownRows) {
    lines.push(
      renderTimelineRow(row, treeBranch(rowIndex++, renderedRows), state),
    );
  }

  return truncateWidgetLines(lines, width);
}

export function renderReviewWidgetText(
  run: ActiveReviewRun,
  state: ReviewPhaseWidgetState,
  phaseNumber: number,
  options: { width?: number; maxLines?: number } = {},
): string[] {
  return widgetLinesToText(
    renderReviewWidgetLines(run, state, phaseNumber, options),
  );
}
