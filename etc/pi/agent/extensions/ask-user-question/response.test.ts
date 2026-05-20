import { describe, expect, test } from "bun:test";
import { CHAT_ABOUT_THIS_LABEL, type AskUserQuestionParams, type QuestionAnswer } from "./types";
import { cancelledResult, completedResult, errorResult, pausedResult } from "./response";

const params: AskUserQuestionParams = {
  questions: [
    {
      question: "Which database should we use?",
      header: "Database",
      options: [
        { label: "SQLite", description: "Local embedded storage." },
        { label: "PostgreSQL", description: "Networked relational database." },
      ],
    },
    {
      question: "Which runtime should host it?",
      header: "Runtime",
      options: [
        { label: "Node", description: "Use Node.js." },
        { label: "Bun", description: "Use Bun." },
      ],
    },
  ],
};

const answer: QuestionAnswer = {
  questionIndex: 0,
  question: params.questions[0].question,
  kind: "option",
  answer: "SQLite",
};

describe("response builders", () => {
  test("builds completed result", () => {
    const result = completedResult([answer]);
    expect(result.details.status).toBe("completed");
    expect(result.details.pendingQuestions).toEqual([]);
    expect(result.content[0].text).toContain("Questionnaire completed");
    expect(result.content[0].text).toContain("SQLite");
  });

  test("builds paused result with pending questions and chat message", () => {
    const result = pausedResult(params, [answer], 1, "I don't understand runtime trade-offs");
    expect(result.details.status).toBe("paused");
    expect(result.details.reason).toBe("chat");
    expect(result.details.activeQuestionIndex).toBe(1);
    expect(result.details.chatMessage).toBe("I don't understand runtime trade-offs");
    expect(result.details.pendingQuestions).toEqual([params.questions[1]]);
    expect(result.content[0].text).toContain("details.pendingQuestions");
  });

  test("keeps the chat question pending without presenting chat as an answer", () => {
    const chatAnswer: QuestionAnswer = {
      questionIndex: 1,
      question: params.questions[1].question,
      kind: "chat",
      answer: CHAT_ABOUT_THIS_LABEL,
      notes: "What does runtime mean?",
    };
    const result = pausedResult(params, [answer, chatAnswer], 1, chatAnswer.notes);
    expect(result.details.answers).toEqual([answer]);
    expect(result.details.pendingQuestions).toEqual([params.questions[1]]);
    expect(result.content[0].text).not.toContain("Q2: User wants to discuss");
  });

  test("builds cancelled result without inventing answers", () => {
    const result = cancelledResult(params);
    expect(result.details.status).toBe("cancelled");
    expect(result.details.reason).toBe("user_cancelled");
    expect(result.details.answers).toEqual([]);
    expect(result.details.pendingQuestions).toEqual(params.questions);
    expect(result.content[0].text).toContain("Do not assume an answer");
  });

  test("builds cancelled result that preserves partial answers", () => {
    const result = cancelledResult(params, [answer]);
    expect(result.details.answers).toEqual([answer]);
    expect(result.details.pendingQuestions).toEqual([params.questions[1]]);
    expect(result.content[0].text).toContain("partial answers");
    expect(result.content[0].text).toContain("pendingQuestions");
  });

  test("builds no-ui error result preserving questions", () => {
    const result = errorResult(params, "Error: UI not available", "no_ui", "no_ui");
    expect(result.details.status).toBe("cancelled");
    expect(result.details.reason).toBe("no_ui");
    expect(result.details.error).toBe("no_ui");
    expect(result.details.pendingQuestions).toEqual(params.questions);
  });

  test("builds validation error result safely for malformed params", () => {
    const nullResult = errorResult(null, "Invalid parameters", "invalid_params");
    expect(nullResult.details.status).toBe("cancelled");
    expect(nullResult.details.error).toBe("invalid_params");
    expect(nullResult.details.pendingQuestions).toEqual([]);

    const malformedQuestionsResult = errorResult({ questions: [null] }, "Invalid parameters", "invalid_params");
    expect(malformedQuestionsResult.details.pendingQuestions).toEqual([]);
  });
});
