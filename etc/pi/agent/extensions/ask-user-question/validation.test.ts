import { describe, expect, test } from "bun:test";
import { type AskUserQuestionParams, TYPE_SOMETHING_LABEL } from "./types";
import { validateAskUserQuestionParams } from "./validation";

function validParams(
  overrides: Partial<AskUserQuestionParams> = {},
): AskUserQuestionParams {
  return {
    questions: [
      {
        question: "Which database should we use?",
        header: "Database",
        options: [
          { label: "SQLite", description: "Local embedded storage." },
          {
            label: "PostgreSQL",
            description: "Networked relational database.",
          },
        ],
      },
    ],
    ...overrides,
  };
}

describe("validateAskUserQuestionParams", () => {
  test("accepts valid params", () => {
    expect(validateAskUserQuestionParams(validParams())).toEqual({ ok: true });
  });

  test("rejects malformed params without throwing", () => {
    const malformedInputs = [
      null,
      {},
      { questions: null },
      { questions: [null] },
      { questions: [{ question: 42 }] },
    ];

    for (const input of malformedInputs) {
      const result = validateAskUserQuestionParams(input);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toBe("invalid_params");
    }
  });

  test("rejects empty question list", () => {
    const result = validateAskUserQuestionParams(
      validParams({ questions: [] }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe("no_questions");
  });

  test("rejects too many questions", () => {
    const q = validParams().questions[0];
    const result = validateAskUserQuestionParams(
      validParams({ questions: [q, q, q, q, q] }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe("too_many_questions");
  });

  test("rejects duplicate question text", () => {
    const q = validParams().questions[0];
    const result = validateAskUserQuestionParams(
      validParams({ questions: [q, { ...q, header: "DB2" }] }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe("duplicate_question");
  });

  test("rejects too few options", () => {
    const q = {
      ...validParams().questions[0],
      options: [{ label: "SQLite", description: "Local." }],
    };
    const result = validateAskUserQuestionParams(
      validParams({ questions: [q] }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe("too_few_options");
  });

  test("rejects duplicate option labels case-insensitively", () => {
    const q = {
      ...validParams().questions[0],
      options: [
        { label: "SQLite", description: "Local." },
        { label: "sqlite", description: "Duplicate." },
      ],
    };
    const result = validateAskUserQuestionParams(
      validParams({ questions: [q] }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe("duplicate_option_label");
  });

  test("rejects reserved labels", () => {
    const q = {
      ...validParams().questions[0],
      options: [
        { label: TYPE_SOMETHING_LABEL, description: "Reserved." },
        { label: "PostgreSQL", description: "Networked." },
      ],
    };
    const result = validateAskUserQuestionParams(
      validParams({ questions: [q] }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe("reserved_label");
  });

  test("rejects empty descriptions", () => {
    const q = {
      ...validParams().questions[0],
      options: [
        { label: "SQLite", description: "" },
        { label: "PostgreSQL", description: "Networked." },
      ],
    };
    const result = validateAskUserQuestionParams(
      validParams({ questions: [q] }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe("empty_description");
  });

  test("rejects previews on multi-select questions", () => {
    const q = {
      ...validParams().questions[0],
      multiSelect: true,
      options: [
        {
          label: "API",
          description: "API surface.",
          preview: "```ts\n/api\n```",
        },
        { label: "CLI", description: "CLI surface." },
      ],
    };
    const result = validateAskUserQuestionParams(
      validParams({ questions: [q] }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe("preview_on_multiselect");
  });
});
