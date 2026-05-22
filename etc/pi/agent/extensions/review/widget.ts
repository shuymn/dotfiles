import {
  clearWidget,
  setAboveEditorWidget,
  type WidgetContext as TuiWidgetContext,
} from "../lib/tui";
import { type ReviewPhaseWidgetState, renderReviewWidgetText } from "./view";
import type { ActiveReviewRun } from "./workflow";

export const REVIEW_WIDGET_KEY = "review-workflow";

export type ReviewWidgetContext = TuiWidgetContext;

export function refreshReviewWidget(
  ctx: ReviewWidgetContext,
  run: ActiveReviewRun,
  state: ReviewPhaseWidgetState,
  phaseNumber: number,
): void {
  setAboveEditorWidget(
    ctx,
    REVIEW_WIDGET_KEY,
    renderReviewWidgetText(run, state, phaseNumber, { maxLines: 12 }),
  );
}

export function clearReviewWidget(ctx: ReviewWidgetContext): void {
  clearWidget(ctx, REVIEW_WIDGET_KEY);
}
