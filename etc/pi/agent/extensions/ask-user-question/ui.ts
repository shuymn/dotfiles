import { Key, matchesKey, truncateToWidth } from "@earendil-works/pi-tui";
import {
  CHAT_ABOUT_THIS_LABEL,
  NEXT_QUESTION_LABEL,
  TYPE_SOMETHING_LABEL,
  type AskUserQuestionParams,
  type QuestionAnswer,
} from "./types";

type ThemeLike = {
  fg: (name: string, text: string) => string;
  bold: (text: string) => string;
};

type TuiLike = { requestRender: () => void };

type Done = (result: AskUiResult | null) => void;

export type AskUiResult =
  | { status: "completed"; answers: QuestionAnswer[] }
  | { status: "paused"; answers: QuestionAnswer[]; activeQuestionIndex: number; chatMessage?: string }
  | { status: "cancelled"; answers: QuestionAnswer[] };

type Mode = "select" | "custom" | "chat" | "summary";

function printableInput(data: string): string | null {
  const bracketedPaste = data.match(/^\x1b\[200~([\s\S]*)\x1b\[201~$/);
  const raw = bracketedPaste ? bracketedPaste[1] : data;
  if (!bracketedPaste && raw.includes("\x1b")) return null;

  const text = [...raw]
    .filter((char) => {
      const code = char.charCodeAt(0);
      return !(code < 32 || code === 0x7f || (code >= 0x80 && code <= 0x9f));
    })
    .join("");
  return text || null;
}

export function createQuestionnaireComponent(
  params: AskUserQuestionParams,
  tui: TuiLike,
  theme: ThemeLike,
  done: Done,
) {
  let questionIndex = 0;
  let selectedIndex = 0;
  let mode: Mode = "select";
  let inputDraft = "";
  let notice: string | undefined;
  const answers: QuestionAnswer[] = [];
  const multiSelections = new Map<number, Set<number>>();

  function refresh() {
    tui.requestRender();
  }

  function currentQuestion() {
    return params.questions[questionIndex];
  }

  function getMultiSet(): Set<number> {
    let set = multiSelections.get(questionIndex);
    if (!set) {
      set = new Set<number>();
      multiSelections.set(questionIndex, set);
    }
    return set;
  }

  function itemCount(): number {
    const q = currentQuestion();
    return q ? q.options.length + 2 : 0;
  }

  function advanceOrComplete() {
    if (questionIndex >= params.questions.length - 1) {
      mode = "summary";
      selectedIndex = 0;
      refresh();
      return;
    }
    questionIndex += 1;
    selectedIndex = 0;
    mode = "select";
    refresh();
  }

  function saveOption(optionIndex: number) {
    const q = currentQuestion();
    const option = q.options[optionIndex];
    if (!option) return;
    notice = undefined;
    answers.push({
      questionIndex,
      question: q.question,
      kind: "option",
      answer: option.label,
      ...(option.preview ? { preview: option.preview } : {}),
    });
    advanceOrComplete();
  }

  function saveMulti() {
    const q = currentQuestion();
    const selected = Array.from(getMultiSet())
      .sort((a, b) => a - b)
      .map((index) => q.options[index]?.label)
      .filter((label): label is string => Boolean(label));
    if (selected.length === 0) {
      notice = "Select at least one option before continuing.";
      refresh();
      return;
    }
    notice = undefined;
    answers.push({ questionIndex, question: q.question, kind: "multi", answer: null, selected });
    advanceOrComplete();
  }

  function enterCustom() {
    mode = "custom";
    inputDraft = "";
    notice = undefined;
    refresh();
  }

  function enterChat() {
    mode = "chat";
    inputDraft = "";
    notice = undefined;
    refresh();
  }

  function submitInput() {
    const q = currentQuestion();
    const trimmed = inputDraft.trim();
    if (mode === "custom") {
      notice = undefined;
      answers.push({ questionIndex, question: q.question, kind: "custom", answer: trimmed || null });
      advanceOrComplete();
      return;
    }

    done({ status: "paused", answers: [...answers], activeQuestionIndex: questionIndex, ...(trimmed ? { chatMessage: trimmed } : {}) });
  }

  function handleSelectEnter() {
    const q = currentQuestion();
    if (!q) return;
    const isMulti = q.multiSelect === true;
    if (isMulti) {
      const submitIndex = q.options.length;
      const chatIndex = q.options.length + 1;
      if (selectedIndex < q.options.length) {
        const set = getMultiSet();
        notice = undefined;
        if (set.has(selectedIndex)) set.delete(selectedIndex);
        else set.add(selectedIndex);
        refresh();
        return;
      }
      if (selectedIndex === submitIndex) saveMulti();
      if (selectedIndex === chatIndex) enterChat();
      return;
    }

    const customIndex = q.options.length;
    const chatIndex = q.options.length + 1;
    if (selectedIndex < q.options.length) saveOption(selectedIndex);
    else if (selectedIndex === customIndex) enterCustom();
    else if (selectedIndex === chatIndex) enterChat();
  }

  function handleInput(data: string) {
    if (mode === "summary") {
      if (matchesKey(data, Key.enter)) done({ status: "completed", answers: [...answers] });
      else if (matchesKey(data, Key.escape)) done({ status: "cancelled", answers: [...answers] });
      return;
    }

    if (mode === "custom" || mode === "chat") {
      if (matchesKey(data, Key.enter)) {
        submitInput();
        return;
      }
      if (matchesKey(data, Key.escape)) {
        mode = "select";
        inputDraft = "";
        refresh();
        return;
      }
      if (matchesKey(data, Key.backspace) || matchesKey(data, Key.ctrl("h"))) {
        inputDraft = [...inputDraft].slice(0, -1).join("");
        refresh();
        return;
      }
      const printable = printableInput(data);
      if (printable) {
        inputDraft += printable;
        refresh();
      }
      return;
    }

    if (matchesKey(data, Key.escape)) {
      done({ status: "cancelled", answers: [...answers] });
      return;
    }
    if (matchesKey(data, Key.up)) {
      selectedIndex = Math.max(0, selectedIndex - 1);
      refresh();
      return;
    }
    if (matchesKey(data, Key.down)) {
      selectedIndex = Math.min(itemCount() - 1, selectedIndex + 1);
      refresh();
      return;
    }
    if (matchesKey(data, Key.space) && currentQuestion()?.multiSelect === true && selectedIndex < currentQuestion().options.length) {
      const set = getMultiSet();
      notice = undefined;
      if (set.has(selectedIndex)) set.delete(selectedIndex);
      else set.add(selectedIndex);
      refresh();
      return;
    }
    if (matchesKey(data, Key.enter)) handleSelectEnter();
  }

  function renderOptionLine(width: number, index: number, label: string, description?: string, checked?: boolean): string[] {
    const selected = index === selectedIndex;
    const pointer = selected ? theme.fg("accent", "> ") : "  ";
    const checkbox = checked === undefined ? "" : checked ? theme.fg("success", "[✓] ") : theme.fg("dim", "[ ] ");
    const title = selected ? theme.fg("accent", theme.bold(label)) : theme.fg("text", label);
    const lines = [truncateToWidth(`${pointer}${checkbox}${index + 1}. ${title}`, width)];
    if (description) lines.push(truncateToWidth(`     ${theme.fg("muted", description)}`, width));
    return lines;
  }

  function render(width: number): string[] {
    const q = currentQuestion();
    const lines: string[] = [];
    const add = (line = "") => lines.push(truncateToWidth(line, width));

    add(theme.fg("accent", "─".repeat(width)));
    add(`${theme.fg("toolTitle", theme.bold("ask_user_question"))} ${theme.fg("muted", `${questionIndex + 1}/${params.questions.length}`)}`);
    add("");

    if (mode === "summary") {
      add(theme.fg("success", theme.bold("Ready to submit")));
      add("");
      for (const answer of answers) {
        const value = answer.kind === "multi" ? answer.selected.join(", ") : answer.answer ?? "(no response)";
        add(`Q${answer.questionIndex + 1}: ${value}`);
      }
      add("");
      add(theme.fg("dim", "Enter submit • Esc cancel"));
      add(theme.fg("accent", "─".repeat(width)));
      return lines;
    }

    if (!q) {
      add(theme.fg("warning", "No question"));
      return lines;
    }

    add(theme.fg("accent", theme.bold(q.header)));
    add(theme.fg("text", theme.bold(q.question)));
    add("");

    if (mode === "custom" || mode === "chat") {
      add(theme.fg("accent", mode === "custom" ? "Type your answer:" : "What would you like to discuss or clarify?"));
      add(inputDraft || theme.fg("dim", "(empty)"));
      add("");
      add(theme.fg("dim", "Enter submit • Esc back"));
      add(theme.fg("accent", "─".repeat(width)));
      return lines;
    }

    if (notice) {
      add(theme.fg("warning", notice));
      add("");
    }

    if (q.multiSelect === true) {
      const set = getMultiSet();
      q.options.forEach((option, index) => lines.push(...renderOptionLine(width, index, option.label, option.description, set.has(index))));
      lines.push(...renderOptionLine(width, q.options.length, NEXT_QUESTION_LABEL, "Submit selected options."));
      lines.push(...renderOptionLine(width, q.options.length + 1, CHAT_ABOUT_THIS_LABEL, "Pause and discuss this question."));
      add("");
      add(theme.fg("dim", "↑↓ navigate • Space toggle • Enter confirm • Esc cancel"));
    } else {
      q.options.forEach((option, index) => {
        lines.push(...renderOptionLine(width, index, option.label, option.description));
        if (option.preview && index === selectedIndex) {
          add(`     ${theme.fg("dim", "Preview:")}`);
          for (const previewLine of option.preview.split("\n").slice(0, 8)) add(`     ${theme.fg("muted", previewLine)}`);
        }
      });
      lines.push(...renderOptionLine(width, q.options.length, TYPE_SOMETHING_LABEL, "Enter a custom answer."));
      lines.push(...renderOptionLine(width, q.options.length + 1, CHAT_ABOUT_THIS_LABEL, "Pause and discuss this question."));
      add("");
      add(theme.fg("dim", "↑↓ navigate • Enter select • Esc cancel"));
    }

    add(theme.fg("accent", "─".repeat(width)));
    return lines;
  }

  return { render, handleInput, invalidate: refresh };
}
