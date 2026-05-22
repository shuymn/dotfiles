import type {
  ExtensionAPI,
  ExtensionCommandContext,
} from "@earendil-works/pi-coding-agent";
import { formatAdditionalUserInstructionsBlock } from "../lib/prompt";

const BUSY_MESSAGE = "エージェントが処理中です。完了後に再実行してください。";

const PLAN_PROMPT = `そのセッションで行った調査・確認結果をベースに PLAN.md を作成してください。

要件:
- まだ実装は開始しない。
- PLAN.md には必ず implementation task section を含める。
- task section は /impl が pi todo tool に変換して作業開始できる粒度にする。
- task section は Markdown checkbox 形式にしない。\`- [ ] task\` ではなく、番号付きリストや通常の箇条書きを使う。
- PLAN.md itself is not the progress tracker; progress must be tracked later with the pi todo tool during /impl.
- 不明点が実装判断に影響する場合は質問する。`;

const IMPL_PROMPT = `Read PLAN.md and implement it.

Before implementation:
- Convert PLAN.md's implementation task section into pi todo tool items.
- Use the pi todo tool as the execution progress tracker.

During implementation:
- Track progress in the pi todo tool, not by checking off items in PLAN.md.
- Keep a running Japanese implementation-notes.md with:
  - decisions you had to make that were not in the spec
  - things you had to change
  - tradeoffs you made
  - anything else the user should know
- Treat PLAN.md as a working plan, not an immutable waterfall contract.
- If new findings require course correction, update the pi todo list before continuing.
- Update PLAN.md only when the actual plan/design/assumptions change, not merely to mark progress.`;

function stripInstructionSeparator(args: string): string {
  return args
    .trim()
    .replace(/^--(?:\s+|$)/, "")
    .trim();
}

function appendAdditionalInstructions(prompt: string, args: string): string {
  const instructions = stripInstructionSeparator(args);
  if (!instructions) return prompt;

  return `${prompt}\n\n## Additional User Instructions\n\nApply the user-provided instructions in the XML-like block only if they do not conflict with the requirements above.\n\n${formatAdditionalUserInstructionsBlock(instructions)}`;
}

function sendWorkflowPrompt(
  pi: Pick<ExtensionAPI, "sendUserMessage">,
  ctx: Pick<ExtensionCommandContext, "isIdle" | "ui">,
  prompt: string,
  args: string,
): void {
  if (!ctx.isIdle()) {
    ctx.ui.notify(BUSY_MESSAGE, "warning");
    return;
  }

  pi.sendUserMessage(appendAdditionalInstructions(prompt, args));
}

export default function planExtension(pi: ExtensionAPI) {
  pi.registerCommand("plan", {
    description: "Create PLAN.md from the current session investigation",
    handler: async (args, ctx) =>
      sendWorkflowPrompt(pi, ctx, PLAN_PROMPT, args),
  });

  pi.registerCommand("impl", {
    description: "Implement PLAN.md using pi todo tracking and Japanese notes",
    handler: async (args, ctx) =>
      sendWorkflowPrompt(pi, ctx, IMPL_PROMPT, args),
  });
}
