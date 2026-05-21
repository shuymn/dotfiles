import { complete } from "@earendil-works/pi-ai";
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import {
  extractTextBlocks,
  extractUserText,
  MAX_TITLE_CHARS,
  sanitizeSessionName,
  shouldArmSessionTitle,
} from "./title";

const TITLE_MODEL_PROVIDER = "openai-codex";
const TITLE_MODEL_ID = "gpt-5.3-codex-spark";
const TITLE_REASONING_EFFORT = "low";
const TITLE_TIMEOUT_MS = 15_000;
const TITLE_TOOL_NAME = "set_session_title";
const SKIP_SESSION_TITLE_FLAGS = ["commit", "create-pr"] as const;

const titleTool = {
  name: TITLE_TOOL_NAME,
  description: "Return the generated session title.",
  parameters: Type.Object({
    title: Type.String({
      minLength: 1,
      maxLength: MAX_TITLE_CHARS,
      description: "Concise session title",
    }),
  }),
};

const TITLE_SYSTEM_PROMPT = `Create a concise, searchable title for a coding-agent session.
Call the ${TITLE_TOOL_NAME} tool with exactly one title based only on the user's first message.

Rules:
- Prefer 2 to 6 words
- Use the same language as the user's message when practical
- Include the task, feature, bug, file, package, command, model, or error when clear
- Avoid generic titles like Coding Help, Fix Bug, Update Code, or New Session
- No quotes
- No markdown
- No labels like Title:
- No trailing punctuation
- Maximum ${MAX_TITLE_CHARS} characters`;

export default function sessionTitleExtension(pi: ExtensionAPI): void {
  let sessionToken = 0;
  let armed = false;
  let pending = false;
  let activeController: AbortController | undefined;

  function abortActiveGeneration() {
    activeController?.abort();
    activeController = undefined;
  }

  pi.on("session_start", async (event, ctx) => {
    abortActiveGeneration();
    sessionToken += 1;
    pending = false;
    if (shouldSkipSessionTitle(pi)) {
      armed = false;
      return;
    }
    armed = shouldArmSessionTitle(
      event.reason,
      ctx.sessionManager.getBranch(),
      pi.getSessionName(),
    );
  });

  pi.on("session_shutdown", async () => {
    abortActiveGeneration();
    sessionToken += 1;
    armed = false;
    pending = false;
  });

  pi.on("message_end", async (event, ctx) => {
    if (!armed || pending || pi.getSessionName()) return;
    if (event.message.role !== "user") return;

    const prompt = extractUserText(event.message.content);
    armed = false;
    if (!prompt) return;

    pending = true;
    const token = sessionToken;
    const controller = new AbortController();
    activeController = controller;

    void generateSessionName(prompt, ctx, controller)
      .then((name) => {
        if (!name) return;
        if (token !== sessionToken) return;
        if (pi.getSessionName()) return;
        pi.setSessionName(name);
      })
      .catch(() => undefined)
      .finally(() => {
        if (activeController === controller) activeController = undefined;
        if (token === sessionToken) pending = false;
      });
  });
}

function shouldSkipSessionTitle(pi: ExtensionAPI): boolean {
  return SKIP_SESSION_TITLE_FLAGS.some((flag) => pi.getFlag(flag) === true);
}

async function generateSessionName(
  prompt: string,
  ctx: ExtensionContext,
  abortController: AbortController,
): Promise<string | undefined> {
  const model = ctx.modelRegistry.find(TITLE_MODEL_PROVIDER, TITLE_MODEL_ID);
  if (!model) return undefined;

  const auth = await ctx.modelRegistry.getApiKeyAndHeaders(model);
  if (abortController.signal.aborted) return undefined;
  if (!auth.ok || !auth.apiKey) return undefined;

  const timeout = setTimeout(() => abortController.abort(), TITLE_TIMEOUT_MS);

  try {
    const response = await complete(
      model,
      {
        systemPrompt: TITLE_SYSTEM_PROMPT,
        messages: [
          {
            role: "user",
            content: [{ type: "text", text: prompt }],
            timestamp: Date.now(),
          },
        ],
        tools: [titleTool],
      },
      {
        apiKey: auth.apiKey,
        headers: auth.headers,
        reasoningEffort: TITLE_REASONING_EFFORT,
        signal: abortController.signal,
        timeoutMs: TITLE_TIMEOUT_MS,
      },
    );

    return (
      extractStructuredTitle(response.content) ??
      extractTextTitle(response.content)
    );
  } finally {
    clearTimeout(timeout);
  }
}

function extractStructuredTitle(content: unknown[]): string | undefined {
  for (const part of content) {
    if (!isTitleToolCall(part)) continue;
    const title = sanitizeSessionName(part.arguments.title);
    if (title) return title;
  }
  return undefined;
}

function isTitleToolCall(
  part: unknown,
): part is { type: "toolCall"; name: string; arguments: { title: string } } {
  return Boolean(
    part &&
      typeof part === "object" &&
      "type" in part &&
      part.type === "toolCall" &&
      "name" in part &&
      part.name === TITLE_TOOL_NAME &&
      "arguments" in part &&
      part.arguments &&
      typeof part.arguments === "object" &&
      "title" in part.arguments &&
      typeof part.arguments.title === "string",
  );
}

function extractTextTitle(content: unknown[]): string | undefined {
  return sanitizeSessionName(extractTextBlocks(content).trim());
}
