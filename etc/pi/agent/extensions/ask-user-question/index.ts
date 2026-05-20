import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Text } from "@earendil-works/pi-tui";
import {
  AskUserQuestionParamsSchema,
  CHAT_ABOUT_THIS_LABEL,
  NEXT_QUESTION_LABEL,
  OTHER_LABEL,
  TYPE_SOMETHING_LABEL,
  type AskUserQuestionParams,
  type QuestionnaireResult,
} from "./types";
import { cancelledResult, completedResult, errorResult, pausedResult } from "./response";
import { createQuestionnaireComponent } from "./ui";
import { validateAskUserQuestionParams } from "./validation";

const ERROR_NO_UI = "Error: UI not available (running in non-interactive mode)";

export default function askUserQuestion(pi: ExtensionAPI) {
  pi.registerTool({
    name: "ask_user_question",
    label: "Ask User Question",
    description: `Ask the user one or more structured questions during execution. Use when implementation-relevant requirements or decisions are ambiguous.

Usage notes:
- Users can type a custom answer for single-select questions or choose "${CHAT_ABOUT_THIS_LABEL}" to pause the questionnaire and continue in free-form conversation.
- Multi-select questions accept listed options only; use "${CHAT_ABOUT_THIS_LABEL}" when the user needs to discuss an unlisted answer.
- Do not author reserved labels such as "${OTHER_LABEL}", "${TYPE_SOMETHING_LABEL}", "${CHAT_ABOUT_THIS_LABEL}", or "${NEXT_QUESTION_LABEL}"; the tool adds runtime controls.
- Use multiSelect: true when multiple answers are valid. Option previews are supported only for single-select questions.
- If you recommend a specific option, make it the first option and append "(Recommended)" to the label.`,
    promptSnippet:
      "Ask the user up to 4 structured questions when implementation-relevant requirements or decisions are ambiguous",
    promptGuidelines: [
      "Use ask_user_question when ambiguity materially affects implementation, architecture, scope, data loss, or user-visible behavior.",
      "Do not use ask_user_question for trivial choices that can be safely assumed.",
      "Group related clarifying questions into one invocation; do not stack multiple ask_user_question calls back-to-back.",
      "Each ask_user_question question must have 2-4 options. Each option must have a concise label and a description explaining the trade-off.",
      `Do not author reserved labels such as ${OTHER_LABEL}, ${TYPE_SOMETHING_LABEL}, ${CHAT_ABOUT_THIS_LABEL}, or ${NEXT_QUESTION_LABEL}; ask_user_question adds runtime sentinel rows.`,
      `If the user selects ${CHAT_ABOUT_THIS_LABEL}, stop the questionnaire flow and discuss normally. Do not immediately call ask_user_question again.`,
      "When resuming after a paused ask_user_question result, reuse details.pendingQuestions; do not regenerate all questions from memory.",
    ],
    parameters: AskUserQuestionParamsSchema as any,

    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const validation = validateAskUserQuestionParams(params);
      if (!validation.ok) return errorResult(params, validation.message, validation.error);

      const typed = params as AskUserQuestionParams;
      if (!ctx.hasUI) return errorResult(typed, ERROR_NO_UI, "no_ui", "no_ui");

      const result = await ctx.ui.custom((tui, theme, _keybindings, done) =>
        createQuestionnaireComponent(typed, tui, theme, done),
      );

      if (!result || result.status === "cancelled") return cancelledResult(typed, result?.answers ?? []);
      if (result.status === "paused") {
        return pausedResult(typed, result.answers, result.activeQuestionIndex, result.chatMessage);
      }
      return completedResult(result.answers);
    },

    renderCall(args, theme) {
      const questions = Array.isArray((args as Partial<AskUserQuestionParams>).questions)
        ? (args as Partial<AskUserQuestionParams>).questions ?? []
        : [];
      const labels = questions.map((q) => q.header || q.question).join(", ");
      const text =
        theme.fg("toolTitle", theme.bold("ask_user_question ")) +
        theme.fg("muted", `${questions.length} question${questions.length === 1 ? "" : "s"}`) +
        (labels ? theme.fg("dim", ` (${labels})`) : "");
      return new Text(text, 0, 0);
    },

    renderResult(result, _options, theme) {
      const details = result.details as QuestionnaireResult | undefined;
      if (!details) {
        const first = result.content[0];
        return new Text(first?.type === "text" ? first.text : "", 0, 0);
      }

      if (details.status === "paused") {
        const suffix = details.chatMessage ? `: ${details.chatMessage}` : "";
        return new Text(theme.fg("warning", "Paused for discussion") + theme.fg("muted", suffix), 0, 0);
      }

      if (details.status === "cancelled") {
        const reason = details.error ? ` (${details.error})` : "";
        return new Text(theme.fg("warning", `Cancelled${reason}`), 0, 0);
      }

      const lines = details.answers.map((answer) => {
        const value = answer.kind === "multi" ? answer.selected.join(", ") : answer.answer ?? "(no response)";
        return `${theme.fg("success", "✓")} Q${answer.questionIndex + 1}: ${theme.fg("accent", value)}`;
      });
      return new Text(lines.join("\n"), 0, 0);
    },
  });
}
