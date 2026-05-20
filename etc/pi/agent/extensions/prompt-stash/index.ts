import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { truncateToWidth } from "@earendil-works/pi-tui";

const CUSTOM_TYPE = "prompt-stash-state";
const MAX_STASHES = 20;

type StashStateEntry = {
  stack: string[];
};

function truncateForNotice(text: string): string {
  return truncateToWidth(text.replace(/\s+/g, " ").trim(), 80, "...");
}

function restoreState(ctx: ExtensionContext): string[] {
  const branch = ctx.sessionManager.getBranch();
  for (let i = branch.length - 1; i >= 0; i -= 1) {
    const entry = branch[i];
    if (entry.type !== "custom" || entry.customType !== CUSTOM_TYPE) continue;
    const data = entry.data as Partial<StashStateEntry> | undefined;
    if (!Array.isArray(data?.stack)) continue;

    return data.stack
      .filter((item): item is string => typeof item === "string")
      .slice(-MAX_STASHES);
  }
  return [];
}

export default function (pi: ExtensionAPI) {
  let stack: string[] = [];

  const persist = () => {
    pi.appendEntry(CUSTOM_TYPE, { stack: stack.slice(-MAX_STASHES) });
  };

  const restoreLatest = (ctx: ExtensionContext) => {
    if (stack.length === 0) return;

    const text = stack[stack.length - 1];
    if (!text) {
      stack.pop();
      return;
    }

    const current = ctx.ui.getEditorText();
    if (current.length > 0) {
      ctx.ui.notify("Prompt stash not restored because the editor is not empty.", "warning");
      return;
    }

    stack.pop();
    ctx.ui.setEditorText(text);
    persist();
    ctx.ui.notify(`Restored stashed prompt: ${truncateForNotice(text)}`, "info");
  };

  pi.on("session_start", (_event, ctx) => {
    stack = restoreState(ctx);
  });

  pi.registerShortcut("ctrl+s", {
    description: "Stash current prompt buffer and clear the editor",
    handler: (ctx) => {
      if (stack.length > 0) {
        restoreLatest(ctx);
        return;
      }

      const text = ctx.ui.getEditorText();
      if (!text.trim()) {
        ctx.ui.notify("Nothing to stash", "info");
        return;
      }

      stack.push(text);
      stack = stack.slice(-MAX_STASHES);
      ctx.ui.setEditorText("");
      persist();
      ctx.ui.notify(`Stashed prompt: ${truncateForNotice(text)}`, "info");
    },
  });

  pi.on("agent_start", (_event, ctx) => {
    if (stack.length === 0) return;
    restoreLatest(ctx);
  });

  pi.on("user_bash", (_event, ctx) => {
    if (stack.length === 0) return;
    restoreLatest(ctx);
  });
}
