import {
  clearWidget,
  setAboveEditorWidget,
  type WidgetContext as TuiWidgetContext,
} from "../lib/tui";
import type { TodoState } from "./state";
import { renderWidgetText } from "./view";

export const TODO_WIDGET_KEY = "todo";

export type WidgetContext = TuiWidgetContext & { hasUI?: boolean };

export function refreshTodoWidget(
  ctx: WidgetContext,
  state: TodoState,
  options: { suppress?: boolean } = {},
): void {
  if (ctx.hasUI === false) return;
  if (options.suppress) {
    clearWidget(ctx, TODO_WIDGET_KEY);
    return;
  }
  const lines = renderWidgetText(state, { maxLines: 12 });
  if (!lines) {
    clearWidget(ctx, TODO_WIDGET_KEY);
    return;
  }
  setAboveEditorWidget(ctx, TODO_WIDGET_KEY, lines);
}
