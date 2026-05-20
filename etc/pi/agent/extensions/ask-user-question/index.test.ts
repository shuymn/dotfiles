import { describe, expect, mock, test } from "bun:test";
import type {
  AskUserQuestionParams,
  QuestionAnswer,
  QuestionnaireResult,
} from "./types";

mock.module("@earendil-works/pi-tui", () => ({
  Text: class {
    constructor(public value: string) {}
  },
  Key: {
    enter: "enter",
    escape: "escape",
    backspace: "backspace",
    up: "up",
    down: "down",
    space: "space",
    ctrl: (key: string) => `ctrl-${key}`,
  },
  matchesKey: (data: string, key: string) => data === key,
  truncateToWidth: (text: string, width: number) => text.slice(0, width),
  // ui.ts now imports printableInput from ../lib/tui, which statically imports
  // these from pi-tui. Provide stubs so the named imports resolve; they are
  // not exercised by the questionnaire component under test.
  Input: class {},
  SelectList: class {},
  fuzzyFilter: (items: unknown[]) => items,
}));

mock.module("@earendil-works/pi-coding-agent", () => ({}));

type ToolDefinition = {
  name: string;
  label: string;
  description: string;
  promptSnippet: string;
  promptGuidelines: string[];
  parameters: unknown;
  execute: (
    toolCallId: string,
    params: unknown,
    signal: AbortSignal | undefined,
    onUpdate: unknown,
    ctx: {
      hasUI: boolean;
      ui?: {
        custom: (
          factory: (...args: any[]) => unknown,
        ) => Promise<unknown> | unknown;
      };
    },
  ) => Promise<{
    content: Array<{ type: "text"; text: string }>;
    details: QuestionnaireResult;
  }>;
  renderCall: (args: unknown, theme: Theme) => { value: string };
  renderResult: (
    result: {
      content: Array<{ type: "text"; text: string }>;
      details?: unknown;
    },
    options: unknown,
    theme: Theme,
  ) => { value: string };
};

type Theme = {
  fg: (name: string, text: string) => string;
  bold: (text: string) => string;
};

function createFakePi() {
  const tools = new Map<string, ToolDefinition>();
  return {
    tools,
    registerTool(definition: ToolDefinition) {
      tools.set(definition.name, definition);
    },
  };
}

async function loadTool() {
  const extension = (await import("./index")).default;
  const pi = createFakePi();
  extension(pi as never);
  return pi.tools.get("ask_user_question")!;
}

function validParams(
  overrides: Partial<AskUserQuestionParams> = {},
): AskUserQuestionParams {
  return {
    questions: [
      {
        question: "Which database should we use?",
        header: "Database",
        options: [
          {
            label: "SQLite",
            description: "Local embedded storage.",
            preview: "file.db",
          },
          {
            label: "PostgreSQL",
            description: "Networked relational database.",
          },
        ],
      },
      {
        question: "Which surfaces need tests?",
        header: "Tests",
        multiSelect: true,
        options: [
          { label: "API", description: "Tool execution behavior." },
          { label: "UI", description: "Interactive questionnaire behavior." },
        ],
      },
    ],
    ...overrides,
  };
}

const theme: Theme = {
  fg: (name, text) => `<${name}>${text}</${name}>`,
  bold: (text) => `**${text}**`,
};

describe("ask-user-question extension", () => {
  test("registers a fully described ask_user_question tool", async () => {
    const tool = await loadTool();

    expect(tool.name).toBe("ask_user_question");
    expect(tool.label).toBe("Ask User Question");
    expect(tool.description).toContain("Chat about this");
    expect(tool.promptGuidelines).toContain(
      "Use ask_user_question when ambiguity materially affects implementation, architecture, scope, data loss, or user-visible behavior.",
    );
    expect(tool.parameters).toMatchObject({
      type: "object",
      properties: { questions: { type: "array", minItems: 1, maxItems: 4 } },
    });
  });

  test("returns a structured validation error without opening UI", async () => {
    const tool = await loadTool();
    let customCalled = false;

    const result = await tool.execute(
      "call-1",
      { questions: [] },
      undefined,
      undefined,
      {
        hasUI: true,
        ui: {
          custom: () => {
            customCalled = true;
          },
        },
      },
    );

    expect(customCalled).toBe(false);
    expect(result.content[0].text).toBe("At least one question is required.");
    expect(result.details).toEqual({
      status: "cancelled",
      answers: [],
      pendingQuestions: [],
      reason: "validation_error",
      error: "no_questions",
    });
  });

  test("returns no_ui error for valid params in non-interactive contexts", async () => {
    const tool = await loadTool();
    const params = validParams({ questions: [validParams().questions[0]] });

    const result = await tool.execute("call-1", params, undefined, undefined, {
      hasUI: false,
    });

    expect(result.content[0].text).toBe(
      "Error: UI not available (running in non-interactive mode)",
    );
    expect(result.details).toEqual({
      status: "cancelled",
      answers: [],
      pendingQuestions: params.questions,
      reason: "no_ui",
      error: "no_ui",
    });
  });

  test("maps completed UI answers into tool content and details", async () => {
    const tool = await loadTool();
    const params = validParams();
    const answers: QuestionAnswer[] = [
      {
        questionIndex: 0,
        question: params.questions[0].question,
        kind: "option",
        answer: "SQLite",
        preview: "file.db",
      },
      {
        questionIndex: 1,
        question: params.questions[1].question,
        kind: "multi",
        answer: null,
        selected: ["API", "UI"],
      },
    ];

    const result = await tool.execute("call-1", params, undefined, undefined, {
      hasUI: true,
      ui: { custom: () => ({ status: "completed", answers }) },
    });

    expect(result.content[0].text).toBe(
      "Questionnaire completed.\nQ1: User selected: SQLite\nQ2: User selected: API, UI",
    );
    expect(result.details).toEqual({
      status: "completed",
      answers,
      pendingQuestions: [],
    });
  });

  test("preserves answered and pending questions when the user pauses for chat", async () => {
    const tool = await loadTool();
    const params = validParams();
    const answers: QuestionAnswer[] = [
      {
        questionIndex: 0,
        question: params.questions[0].question,
        kind: "option",
        answer: "PostgreSQL",
      },
      {
        questionIndex: 1,
        question: params.questions[1].question,
        kind: "chat",
        answer: null,
        notes: "Need trade-offs",
      },
    ];

    const result = await tool.execute("call-1", params, undefined, undefined, {
      hasUI: true,
      ui: {
        custom: () => ({
          status: "paused",
          answers,
          activeQuestionIndex: 1,
          chatMessage: "Need trade-offs",
        }),
      },
    });

    expect(result.content[0].text).toContain(
      "The user paused the questionnaire to discuss question 2.",
    );
    expect(result.content[0].text).toContain(
      "Pending questions are preserved in details.pendingQuestions.",
    );
    expect(result.details).toEqual({
      status: "paused",
      answers: [answers[0]],
      pendingQuestions: [params.questions[1]],
      activeQuestionIndex: 1,
      reason: "chat",
      chatMessage: "Need trade-offs",
    });
  });

  test("returns cancellation with partial answers when UI returns null or cancelled", async () => {
    const tool = await loadTool();
    const params = validParams();
    const partial: QuestionAnswer[] = [
      {
        questionIndex: 0,
        question: params.questions[0].question,
        kind: "custom",
        answer: "Use existing DB",
      },
    ];

    const nullResult = await tool.execute(
      "call-1",
      params,
      undefined,
      undefined,
      {
        hasUI: true,
        ui: { custom: () => null },
      },
    );
    expect(nullResult.details).toEqual({
      status: "cancelled",
      answers: [],
      pendingQuestions: params.questions,
      reason: "user_cancelled",
    });

    const cancelledResult = await tool.execute(
      "call-2",
      params,
      undefined,
      undefined,
      {
        hasUI: true,
        ui: { custom: () => ({ status: "cancelled", answers: partial }) },
      },
    );
    expect(cancelledResult.content[0].text).toContain(
      "Use only details.answers as partial answers",
    );
    expect(cancelledResult.details).toEqual({
      status: "cancelled",
      answers: partial,
      pendingQuestions: [params.questions[1]],
      reason: "user_cancelled",
    });
  });

  test("passes params through to the questionnaire component factory", async () => {
    const tool = await loadTool();
    const params = validParams({ questions: [validParams().questions[0]] });
    let renderedLines: string[] | undefined;

    await tool.execute("call-1", params, undefined, undefined, {
      hasUI: true,
      ui: {
        custom: (factory) => {
          const component = factory(
            { requestRender() {} },
            {
              fg: (_name: string, text: string) => text,
              bold: (text: string) => text,
            },
            {},
            () => undefined,
          ) as { render: (width: number) => string[] };
          renderedLines = component.render(80);
          return { status: "cancelled", answers: [] };
        },
      },
    });

    expect(renderedLines).toContain("ask_user_question 1/1");
    expect(renderedLines).toContain("Database");
    expect(renderedLines).toContain("Which database should we use?");
  });

  test("renders calls and results for terminal display", async () => {
    const tool = await loadTool();
    const params = validParams();

    expect(tool.renderCall(params, theme).value).toBe(
      "<toolTitle>**ask_user_question **</toolTitle><muted>2 questions</muted><dim> (Database, Tests)</dim>",
    );
    expect(
      tool.renderCall(
        { questions: [{ question: "Fallback?", options: [] }] },
        theme,
      ).value,
    ).toContain("Fallback?");

    expect(
      tool.renderResult(
        { content: [{ type: "text", text: "raw result" }] },
        undefined,
        theme,
      ).value,
    ).toBe("raw result");
    expect(
      tool.renderResult(
        {
          content: [],
          details: {
            status: "paused",
            answers: [],
            pendingQuestions: [],
            chatMessage: "Why?",
          },
        },
        undefined,
        theme,
      ).value,
    ).toBe("<warning>Paused for discussion</warning><muted>: Why?</muted>");
    expect(
      tool.renderResult(
        {
          content: [],
          details: {
            status: "cancelled",
            answers: [],
            pendingQuestions: [],
            error: "no_ui",
          },
        },
        undefined,
        theme,
      ).value,
    ).toBe("<warning>Cancelled (no_ui)</warning>");
    expect(
      tool.renderResult(
        {
          content: [],
          details: {
            status: "completed",
            answers: [
              {
                questionIndex: 0,
                question: "Q?",
                kind: "multi",
                answer: null,
                selected: ["A", "B"],
              },
            ],
            pendingQuestions: [],
          },
        },
        undefined,
        theme,
      ).value,
    ).toBe("<success>✓</success> Q1: <accent>A, B</accent>");
  });
});
