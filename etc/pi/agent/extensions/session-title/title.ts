import type {
  ExtensionContext,
  SessionStartEvent,
} from "@earendil-works/pi-coding-agent";

const MAX_PROMPT_CHARS = 4_000;
export const MAX_TITLE_CHARS = 60;
const LEGACY_SESSION_TITLE_PREFIX_PATTERN = /^(π\s*-\s*)+/i;

type SessionEntry = ReturnType<
  ExtensionContext["sessionManager"]["getBranch"]
>[number];

export type SessionStartReason = SessionStartEvent["reason"];

export function shouldArmSessionTitle(
  reason: SessionStartReason | undefined,
  entries: SessionEntry[],
  currentName: string | undefined,
): boolean {
  if (currentName?.trim()) return false;
  if (reason !== "startup" && reason !== "new") return false;
  return countUserMessages(entries) === 0;
}

export function countUserMessages(entries: SessionEntry[]): number {
  let count = 0;
  for (const entry of entries) {
    if (entry.type === "message" && entry.message.role === "user") count += 1;
  }
  return count;
}

export function extractUserText(content: unknown): string {
  if (typeof content === "string") return normalizePrompt(content);
  if (!Array.isArray(content)) return "";

  return normalizePrompt(extractTextBlocks(content));
}

export function extractTextBlocks(content: unknown): string {
  if (!Array.isArray(content)) return "";

  return content
    .map((part) => {
      if (!part || typeof part !== "object") return undefined;
      const block = part as { type?: string; text?: string };
      return block.type === "text" && typeof block.text === "string"
        ? block.text
        : undefined;
    })
    .filter((part): part is string => Boolean(part))
    .join("\n");
}

export function sanitizeSessionName(value: string): string | undefined {
  const candidates = value
    .replace(/^\s*```[a-z0-9_-]*\s*/i, "")
    .replace(/```\s*$/g, "")
    .split(/\r?\n/);

  for (const candidate of candidates) {
    const title = sanitizeTitleCandidate(candidate);
    if (title) return title;
  }

  return undefined;
}

function sanitizeTitleCandidate(value: string): string | undefined {
  let title = value
    .trim()
    .replace(/^[-*]\s*/, "")
    .replace(/^(title|session name|タイトル|セッション名)\s*[:：]\s*/i, "")
    .replace(LEGACY_SESSION_TITLE_PREFIX_PATTERN, "")
    .replace(/^[「『'"`]+|[」』'"`]+$/g, "")
    .replace(/[.?!:;,。！？：；、]+$/g, "")
    .replace(/^[「『'"`]+|[」』'"`]+$/g, "")
    .replace(/\s+/g, " ")
    .trim();

  if (!title) return undefined;
  if (title.length <= MAX_TITLE_CHARS) return title;

  title = title.slice(0, MAX_TITLE_CHARS).trimEnd();
  const lastSpace = title.lastIndexOf(" ");
  if (lastSpace > 20) title = title.slice(0, lastSpace);
  return title.trim() || undefined;
}

function normalizePrompt(value: string): string {
  return value.replace(/\r\n/g, "\n").trim().slice(0, MAX_PROMPT_CHARS);
}
