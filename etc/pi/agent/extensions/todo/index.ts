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

  function replayAndRefresh(ctx: WidgetContext & { sessionManager: unknown }) {
    state = replayTodoState(ctx.sessionManager as never);
    refreshTodoWidget(ctx, state);
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
      refreshTodoWidget(ctx, state);
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
      refreshTodoWidget(ctx, state);
    }
  });
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
