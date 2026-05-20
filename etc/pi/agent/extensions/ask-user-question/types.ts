export const MAX_QUESTIONS = 4;
export const MIN_OPTIONS = 2;
export const MAX_OPTIONS = 4;
export const MAX_HEADER_LENGTH = 16;
export const MAX_LABEL_LENGTH = 60;

export const OTHER_LABEL = "Other";
export const TYPE_SOMETHING_LABEL = "Type something.";
export const CHAT_ABOUT_THIS_LABEL = "Chat about this";
export const NEXT_QUESTION_LABEL = "Next question";

export const RESERVED_LABELS = [
  OTHER_LABEL,
  TYPE_SOMETHING_LABEL,
  CHAT_ABOUT_THIS_LABEL,
  NEXT_QUESTION_LABEL,
] as const;

export interface OptionData {
  label: string;
  description: string;
  preview?: string;
}

export interface QuestionData {
  question: string;
  header: string;
  options: OptionData[];
  multiSelect?: boolean;
}

export interface AskUserQuestionParams {
  questions: QuestionData[];
}

export const AskUserQuestionParamsSchema = {
  type: "object",
  properties: {
    questions: {
      type: "array",
      minItems: 1,
      maxItems: MAX_QUESTIONS,
      description: "Questions to ask the user.",
      items: {
        type: "object",
        properties: {
          question: {
            type: "string",
            description:
              "The complete question to ask the user. It should be clear, specific, and end with a question mark.",
          },
          header: {
            type: "string",
            maxLength: MAX_HEADER_LENGTH,
            description: "Short tab/chip label for this question.",
          },
          options: {
            type: "array",
            minItems: MIN_OPTIONS,
            maxItems: MAX_OPTIONS,
            description: "Available choices for this question. Runtime sentinel rows are added by the tool.",
            items: {
              type: "object",
              properties: {
                label: {
                  type: "string",
                  maxLength: MAX_LABEL_LENGTH,
                  description: "Concise display label for this option. Do not use reserved runtime labels.",
                },
                description: {
                  type: "string",
                  description: "Explanation of what this option means or what trade-off it represents.",
                },
                preview: {
                  type: "string",
                  description:
                    "Optional markdown/monospace preview for comparing concrete artifacts. Single-select only.",
                },
              },
              required: ["label", "description"],
              additionalProperties: false,
            },
          },
          multiSelect: {
            type: "boolean",
            default: false,
            description: "Allow the user to select multiple options for this question.",
          },
        },
        required: ["question", "header", "options"],
        additionalProperties: false,
      },
    },
  },
  required: ["questions"],
  additionalProperties: false,
} as const;

export type QuestionAnswer =
  | {
      questionIndex: number;
      question: string;
      kind: "option";
      answer: string;
      preview?: string;
    }
  | {
      questionIndex: number;
      question: string;
      kind: "custom";
      answer: string | null;
    }
  | {
      questionIndex: number;
      question: string;
      kind: "chat";
      answer: string | null;
      notes?: string;
    }
  | {
      questionIndex: number;
      question: string;
      kind: "multi";
      answer: null;
      selected: string[];
    };

export type QuestionnaireStatus = "completed" | "paused" | "cancelled";
export type QuestionnaireReason = "chat" | "user_cancelled" | "validation_error" | "no_ui";
export type QuestionnaireError =
  | "no_ui"
  | "no_questions"
  | "too_many_questions"
  | "too_few_options"
  | "too_many_options"
  | "empty_description"
  | "duplicate_question"
  | "duplicate_option_label"
  | "reserved_label"
  | "preview_on_multiselect"
  | "invalid_params";

export interface QuestionnaireResult {
  status: QuestionnaireStatus;
  answers: QuestionAnswer[];
  pendingQuestions: QuestionData[];
  activeQuestionIndex?: number;
  reason?: QuestionnaireReason;
  chatMessage?: string;
  error?: QuestionnaireError;
}

export type ToolTextResult = {
  content: Array<{ type: "text"; text: string }>;
  details: QuestionnaireResult;
};
