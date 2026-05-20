import {
  type AskUserQuestionParams,
  MAX_OPTIONS,
  MAX_QUESTIONS,
  MIN_OPTIONS,
  type QuestionnaireError,
  RESERVED_LABELS,
} from "./types";

export type ValidationResult =
  | { ok: true }
  | { ok: false; error: QuestionnaireError; message: string };

function normalizeComparable(value: string): string {
  return value.trim().toLowerCase();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function invalidParams(message: string): ValidationResult {
  return { ok: false, error: "invalid_params", message };
}

export function validateAskUserQuestionParams(
  params: unknown,
): ValidationResult {
  if (!isRecord(params) || !Array.isArray(params.questions)) {
    return invalidParams(
      "Invalid ask_user_question parameters: questions must be an array.",
    );
  }

  const typed = params as unknown as AskUserQuestionParams;

  if (typed.questions.length === 0) {
    return {
      ok: false,
      error: "no_questions",
      message: "At least one question is required.",
    };
  }

  if (typed.questions.length > MAX_QUESTIONS) {
    return {
      ok: false,
      error: "too_many_questions",
      message: `At most ${MAX_QUESTIONS} questions are allowed.`,
    };
  }

  const seenQuestions = new Set<string>();
  const reserved = new Set(RESERVED_LABELS.map(normalizeComparable));

  for (const question of typed.questions) {
    if (!isRecord(question)) {
      return invalidParams(
        "Invalid ask_user_question parameters: each question must be an object.",
      );
    }
    if (
      typeof question.question !== "string" ||
      typeof question.header !== "string"
    ) {
      return invalidParams(
        "Invalid ask_user_question parameters: question and header must be strings.",
      );
    }
    if (!Array.isArray(question.options)) {
      return invalidParams(
        "Invalid ask_user_question parameters: options must be an array.",
      );
    }
    if (
      question.multiSelect !== undefined &&
      typeof question.multiSelect !== "boolean"
    ) {
      return invalidParams(
        "Invalid ask_user_question parameters: multiSelect must be a boolean when provided.",
      );
    }

    const questionKey = normalizeComparable(question.question);
    if (seenQuestions.has(questionKey)) {
      return {
        ok: false,
        error: "duplicate_question",
        message: `Duplicate question: ${question.question}`,
      };
    }
    seenQuestions.add(questionKey);

    if (question.options.length < MIN_OPTIONS) {
      return {
        ok: false,
        error: "too_few_options",
        message: `Question "${question.header}" must have at least ${MIN_OPTIONS} options.`,
      };
    }

    if (question.options.length > MAX_OPTIONS) {
      return {
        ok: false,
        error: "too_many_options",
        message: `Question "${question.header}" must have at most ${MAX_OPTIONS} options.`,
      };
    }

    const seenOptionLabels = new Set<string>();
    for (const option of question.options) {
      if (!isRecord(option)) {
        return invalidParams(
          "Invalid ask_user_question parameters: each option must be an object.",
        );
      }
      if (
        typeof option.label !== "string" ||
        typeof option.description !== "string"
      ) {
        return invalidParams(
          "Invalid ask_user_question parameters: option label and description must be strings.",
        );
      }
      if (option.preview !== undefined && typeof option.preview !== "string") {
        return invalidParams(
          "Invalid ask_user_question parameters: option preview must be a string when provided.",
        );
      }

      const labelKey = normalizeComparable(option.label);
      if (reserved.has(labelKey)) {
        return {
          ok: false,
          error: "reserved_label",
          message: `Option label "${option.label}" is reserved for runtime controls.`,
        };
      }
      if (seenOptionLabels.has(labelKey)) {
        return {
          ok: false,
          error: "duplicate_option_label",
          message: `Duplicate option label in "${question.header}": ${option.label}`,
        };
      }
      seenOptionLabels.add(labelKey);

      if (option.description.trim().length === 0) {
        return {
          ok: false,
          error: "empty_description",
          message: `Option "${option.label}" must include a non-empty description.`,
        };
      }

      if (question.multiSelect === true && option.preview?.trim()) {
        return {
          ok: false,
          error: "preview_on_multiselect",
          message: `Option previews are supported only for single-select questions: ${option.label}`,
        };
      }
    }
  }

  return { ok: true };
}
