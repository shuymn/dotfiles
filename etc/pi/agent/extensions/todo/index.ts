import { StringEnum } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { nextActionText, renderTodoReminder } from "./prompt";
import { replayTodoState, TOOL_NAME } from "./replay";
import { inProgressTodo, pendingTodos } from "./selectors";
import {
  applyTodoMutation,
  cloneTodoState,
  EMPTY_TODO_STATE,
  TODO_ACTIONS,
  TODO_STATUSES,
  type TodoOperation,
  type TodoParams,
  type TodoState,
  type TodoToolDetails,
} from "./state";
import {
  refreshTodoWidget,
  TODO_WIDGET_KEY,
  type WidgetContext,
} from "./widget";

const REVIEW_WORKFLOW_EVENT_NAME = "review";
const REVIEW_WORKFLOW_EVENTS = [
  { event: "workflow:started", status: "started", suppress: true },
  { event: "workflow:completed", status: "completed", suppress: false },
  { event: "workflow:failed", status: "failed", suppress: false },
  { event: "workflow:cancelled", status: "cancelled", suppress: false },
] as const;

type ReviewWorkflowLifecycleStatus =
  (typeof REVIEW_WORKFLOW_EVENTS)[number]["status"];

type ReviewWorkflowLifecycleEvent = {
  name?: string;
  status?: string;
};

function isReviewWorkflowLifecycleEvent(
  data: unknown,
  expectedStatus: ReviewWorkflowLifecycleStatus,
): data is ReviewWorkflowLifecycleEvent {
  return (
    typeof data === "object" &&
    data !== null &&
    (data as ReviewWorkflowLifecycleEvent).name ===
      REVIEW_WORKFLOW_EVENT_NAME &&
    (data as ReviewWorkflowLifecycleEvent).status === expectedStatus
  );
}

function formatToolResult(state: TodoState, op: TodoOperation): string {
  const lines: string[] = [];

  switch (op.kind) {
    case "create": {
      const item = state.items.find((candidate) => candidate.id === op.id);
      lines.push(`Created #${op.id}: ${item?.title ?? "todo"}.`);
      break;
    }
    case "update": {
      if (op.toStatus === "completed") {
        lines.push(`Completed #${op.id}: ${op.title}.`);
      } else if (op.toStatus === "cancelled") {
        lines.push(`Cancelled #${op.id}: ${op.title}.`);
      } else {
        lines.push(
          `Updated #${op.id}: ${op.title} (${op.fromStatus} -> ${op.toStatus}).`,
        );
      }
      if (op.autoCleared) {
        lines.push(
          "All todos are closed; todo list was automatically cleared.",
        );
      }
      break;
    }
    case "list":
      lines.push("Current todos:");
      break;
    case "clear":
      lines.push(`Cleared ${op.count} todo${op.count === 1 ? "" : "s"}.`);
      break;
    case "error":
      lines.push(`Todo error: ${op.message}`);
      break;
  }

  if (state.items.length > 0) {
    lines.push(
      "",
      ...state.items.map(
        (item) => `#${item.id} [${item.status}] ${item.title}`,
      ),
    );
  }

  const inProgress = inProgressTodo(state);
  const pending = pendingTodos(state);
  if (
    !inProgress &&
    op.kind === "update" &&
    op.toStatus === "completed" &&
    pending.length > 0
  ) {
    lines.push(
      "",
      "Next pending todos remain:",
      ...pending.map((item) => `#${item.id} ${item.title}`),
      "",
      "Pick one pending todo and mark it in_progress before continuing.",
    );
  } else {
    const nextAction = nextActionText(state);
    if (nextAction) lines.push("", nextAction);
  }

  return lines.join("\n");
}

export default function (pi: ExtensionAPI) {
  let state = cloneTodoState(EMPTY_TODO_STATE);
  let currentUiCtx: WidgetContext | undefined;
  let suppressWidgetForReview = false;

  function refreshWidget(ctx: WidgetContext): void {
    if (ctx.hasUI !== false) currentUiCtx = ctx;
    refreshTodoWidget(ctx, state, { suppress: suppressWidgetForReview });
  }

  function replayAndRefresh(ctx: WidgetContext & { sessionManager: unknown }) {
    state = replayTodoState(ctx.sessionManager as never);
    refreshWidget(ctx);
  }

  function setReviewWidgetSuppression(suppress: boolean): void {
    suppressWidgetForReview = suppress;
    if (currentUiCtx) refreshWidget(currentUiCtx);
  }

  function handleReviewWorkflowLifecycle(
    data: unknown,
    status: ReviewWorkflowLifecycleStatus,
    suppress: boolean,
  ): void {
    if (!isReviewWorkflowLifecycleEvent(data, status)) return;
    setReviewWidgetSuppression(suppress);
  }

  pi.registerTool({
    name: TOOL_NAME,
    label: "Todo",
    description: "Manage a branch-local todo list for multi-step coding work.",
    promptSnippet:
      "Manage a branch-local todo list to plan, track, and continue multi-step coding work.",
    promptGuidelines: [
      "Use todo for non-trivial multi-step coding tasks, user-provided task lists, or work that includes investigation, implementation, and verification.",
      "Skip todo for single trivial tasks and purely conversational requests.",
      "For non-trivial work, think through the approach and create todos that reflect the planned order before starting tool-heavy implementation.",
      "Break broad goals into verifiable work units; avoid a single todo that merely restates the user's whole request.",
      "Update, split, or cancel todos when investigation reveals the original plan is wrong or incomplete.",
      "Before starting implementation, create todos or mark one existing todo in_progress.",
      "Keep at most one todo in_progress. Mark the current todo completed immediately when its work is done.",
      "After completing a todo, pick the next pending todo and mark it in_progress before continuing.",
      "Before final response, ensure no todo is in_progress; if pending todos remain, explicitly report what remains.",
    ],
    parameters: Type.Object({
      action: StringEnum(TODO_ACTIONS, {
        description: "Todo action to perform.",
      }),
      title: Type.Optional(
        Type.String({ description: "Todo title for create or update." }),
      ),
      description: Type.Optional(
        Type.String({ description: "Optional todo details." }),
      ),
      id: Type.Optional(Type.Number({ description: "Todo id for update." })),
      status: Type.Optional(
        StringEnum(TODO_STATUSES, { description: "New status for update." }),
      ),
      activeForm: Type.Optional(
        Type.String({
          description: "Short current-work wording for the active todo.",
        }),
      ),
    }),
    async execute(_toolCallId, params: TodoParams, _signal, _onUpdate, ctx) {
      const result = applyTodoMutation(state, params, Date.now());
      state = result.state;
      const details: TodoToolDetails = {
        action: params.action,
        params: { ...params },
        state: cloneTodoState(state),
        op: result.op,
      };
      refreshWidget(ctx);
      return {
        content: [{ type: "text", text: formatToolResult(state, result.op) }],
        details,
        isError: result.op.kind === "error",
      };
    },
  });

  pi.on("session_start", async (_event, ctx) => replayAndRefresh(ctx));
  pi.on("session_tree", async (_event, ctx) => replayAndRefresh(ctx));
  pi.on("session_compact", async (_event, ctx) => replayAndRefresh(ctx));
  pi.on("session_shutdown", async (_event, ctx) => {
    suppressWidgetForReview = false;
    currentUiCtx = undefined;
    if ((ctx as { hasUI?: boolean } | undefined)?.hasUI === false) return;
    (
      ctx as
        | { ui?: { setWidget?: (key: string, lines: undefined) => void } }
        | undefined
    )?.ui?.setWidget?.(TODO_WIDGET_KEY, undefined);
  });
  pi.on("tool_execution_end", async (event, ctx) => {
    const toolEvent = event as { toolName?: string; isError?: boolean };
    if (toolEvent.toolName === TOOL_NAME && toolEvent.isError !== true) {
      refreshWidget(ctx);
    }
  });

  for (const { event, status, suppress } of REVIEW_WORKFLOW_EVENTS) {
    pi.events.on(event, (data) =>
      handleReviewWorkflowLifecycle(data, status, suppress),
    );
  }

  pi.on("context", async (event) => {
    const reminder = renderTodoReminder(state);
    if (!reminder) return;
    return {
      messages: [
        ...event.messages,
        {
          role: "user",
          content: [{ type: "text", text: reminder }],
          timestamp: Date.now(),
        },
      ],
    };
  });
}
