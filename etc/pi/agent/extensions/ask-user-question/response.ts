import type {
  AskUserQuestionParams,
  QuestionAnswer,
  QuestionData,
  QuestionnaireError,
  QuestionnaireResult,
  ToolTextResult,
} from "./types";

function isRealAnswer(answer: QuestionAnswer): boolean {
  return answer.kind === "option" || answer.kind === "custom" || answer.kind === "multi";
}

function answeredQuestionIndexes(answers: QuestionAnswer[]): Set<number> {
  return new Set(answers.filter(isRealAnswer).map((answer) => answer.questionIndex));
}

function isQuestionDataLike(value: unknown): value is QuestionData {
  if (!value || typeof value !== "object") return false;
  const question = value as Partial<QuestionData>;
  return typeof question.question === "string" && typeof question.header === "string" && Array.isArray(question.options);
}

function safePendingQuestions(params: unknown): QuestionData[] {
  if (!params || typeof params !== "object") return [];
  const questions = (params as { questions?: unknown }).questions;
  if (!Array.isArray(questions) || !questions.every(isQuestionDataLike)) return [];
  return questions;
}

export function pendingQuestionsFrom(params: AskUserQuestionParams, answers: QuestionAnswer[]): QuestionData[] {
  const answered = answeredQuestionIndexes(answers);
  return params.questions.filter((_question, index) => !answered.has(index));
}

function formatAnswer(answer: QuestionAnswer): string {
  const label = `Q${answer.questionIndex + 1}`;
  switch (answer.kind) {
    case "option":
      return `${label}: User selected: ${answer.answer}`;
    case "custom":
      return `${label}: User wrote: ${answer.answer ?? "(no response)"}`;
    case "chat":
      return `${label}: User wants to discuss this question${answer.notes ? `: ${answer.notes}` : "."}`;
    case "multi":
      return `${label}: User selected: ${answer.selected.join(", ")}`;
    default: {
      const _exhaustive: never = answer;
      return _exhaustive;
    }
  }
}

export function completedResult(answers: QuestionAnswer[]): ToolTextResult {
  const details: QuestionnaireResult = {
    status: "completed",
    answers,
    pendingQuestions: [],
  };

  const answerText = answers.length > 0 ? answers.map(formatAnswer).join("\n") : "No answers were provided.";
  return {
    content: [{ type: "text", text: `Questionnaire completed.\n${answerText}` }],
    details,
  };
}

export function pausedResult(
  params: AskUserQuestionParams,
  answers: QuestionAnswer[],
  activeQuestionIndex: number,
  chatMessage?: string,
): ToolTextResult {
  const realAnswers = answers.filter(isRealAnswer);
  const pendingQuestions = pendingQuestionsFrom(params, realAnswers);
  const details: QuestionnaireResult = {
    status: "paused",
    answers: realAnswers,
    pendingQuestions,
    activeQuestionIndex,
    reason: "chat",
    ...(chatMessage ? { chatMessage } : {}),
  };

  const answeredText = realAnswers.length > 0 ? realAnswers.map(formatAnswer).join("\n") : "- None yet";
  const concern = chatMessage ? `\nUser concern: ${chatMessage}\n` : "\n";
  return {
    content: [
      {
        type: "text",
        text:
          `The user paused the questionnaire to discuss question ${activeQuestionIndex + 1}.` +
          `${concern}` +
          `Already answered:\n${answeredText}\n\n` +
          "Pending questions are preserved in details.pendingQuestions. Do not recreate the questionnaire from memory. First discuss the user's concern in normal chat. When ready, call ask_user_question again using the preserved pendingQuestions only.",
      },
    ],
    details,
  };
}

export function cancelledResult(params: AskUserQuestionParams, answers: QuestionAnswer[] = []): ToolTextResult {
  const details: QuestionnaireResult = {
    status: "cancelled",
    answers,
    pendingQuestions: pendingQuestionsFrom(params, answers),
    reason: "user_cancelled",
  };

  const text =
    answers.length === 0
      ? "The user cancelled the questionnaire. Do not assume an answer."
      : "The user cancelled before completing the questionnaire. Use only details.answers as partial answers; do not assume answers for details.pendingQuestions.";

  return {
    content: [{ type: "text", text }],
    details,
  };
}

export function errorResult(
  params: unknown,
  message: string,
  error: QuestionnaireError,
  reason: "validation_error" | "no_ui" = "validation_error",
): ToolTextResult {
  return {
    content: [{ type: "text", text: message }],
    details: {
      status: "cancelled",
      answers: [],
      pendingQuestions: safePendingQuestions(params),
      reason,
      error,
    },
  };
}
