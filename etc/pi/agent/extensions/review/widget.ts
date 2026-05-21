import { clearWidget } from "../lib/tui";
import { type ReviewPhaseWidgetState, renderReviewWidgetText } from "./view";
import type { ActiveReviewRun } from "./workflow";

export const REVIEW_WIDGET_KEY = "review-workflow";

export type ReviewWidgetContext = {
  ui: {
    setWidget(
      key: string,
      content: string[] | undefined,
      options?: { placement?: "aboveEditor" | "belowEditor" },
    ): void;
  };
};

export function refreshReviewWidget(
  ctx: ReviewWidgetContext,
  run: ActiveReviewRun,
  state: ReviewPhaseWidgetState,
  phaseNumber: number,
): void {
  ctx.ui.setWidget(
    REVIEW_WIDGET_KEY,
    renderReviewWidgetText(run, state, phaseNumber, { maxLines: 12 }),
    { placement: "aboveEditor" },
  );
}

export function clearReviewWidget(ctx: ReviewWidgetContext): void {
  clearWidget(ctx, REVIEW_WIDGET_KEY);
}
