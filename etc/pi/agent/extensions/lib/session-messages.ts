function collectTextParts(value: unknown, output: string[]): void {
  if (typeof value === "string") {
    output.push(value);
    return;
  }
  if (!value || typeof value !== "object") return;

  if (Array.isArray(value)) {
    for (const item of value) collectTextParts(item, output);
    return;
  }

  const record = value as Record<string, unknown>;
  if (record.type === "text" && typeof record.text === "string") {
    output.push(record.text);
  }
}

function findLatestAssistantMessageText(value: unknown): string | undefined {
  if (!value || typeof value !== "object") return undefined;

  if (Array.isArray(value)) {
    for (let index = value.length - 1; index >= 0; index -= 1) {
      const text = findLatestAssistantMessageText(value[index]);
      if (text) return text;
    }
    return undefined;
  }

  const record = value as Record<string, unknown>;
  if (record.role === "assistant") {
    const textParts: string[] = [];
    collectTextParts(record.content, textParts);
    return textParts.length > 0 ? textParts.join("\n") : undefined;
  }

  const children = Object.values(record);
  for (let index = children.length - 1; index >= 0; index -= 1) {
    const text = findLatestAssistantMessageText(children[index]);
    if (text) return text;
  }

  return undefined;
}

export function getLatestAssistantMessageText(
  messages: unknown,
): string | undefined {
  try {
    return findLatestAssistantMessageText(messages);
  } catch {
    return undefined;
  }
}
