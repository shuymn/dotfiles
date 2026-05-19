import { randomUUID } from "node:crypto";
import {
  createAgentSession,
  DefaultResourceLoader,
  getAgentDir,
  SessionManager,
  SettingsManager,
  type AgentSession,
  type AgentSessionEvent,
  type ExtensionAPI,
  type ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const SUBAGENT_TOOLS = ["read", "write", "edit", "bash"];
type SubagentStatus = "running" | "completed" | "error" | "stopped";

type SubagentRecord = {
  id: string;
  description: string;
  status: SubagentStatus;
  startedAt: number;
  completedAt?: number;
  result?: string;
  error?: string;
  session?: AgentSession;
  promise: Promise<void>;
  abortController: AbortController;
};

const records = new Map<string, SubagentRecord>();

function textResult(text: string, details?: Record<string, unknown>) {
  return {
    content: [{ type: "text" as const, text }],
    details: details ?? {},
  };
}

function makeId(): string {
  return randomUUID().slice(0, 8);
}

function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return `${text.slice(0, maxChars)}\n...(truncated; call get_subagent_result for full output)`;
}

function extractText(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((part: any) => {
      if (part?.type === "text") return part.text ?? "";
      return "";
    })
    .filter(Boolean)
    .join("\n");
}

function getLastAssistantText(session: AgentSession): string {
  for (let i = session.messages.length - 1; i >= 0; i--) {
    const message = session.messages[i];
    if (message.role !== "assistant") continue;
    const text = extractText(message.content).trim();
    if (text) return text;
  }
  return "";
}

function collectAssistantText(
  session: AgentSession,
  onUpdate?: (text: string) => void,
) {
  let current = "";
  const unsubscribe = session.subscribe((event: AgentSessionEvent) => {
    if (event.type === "message_start") current = "";
    if (
      event.type === "message_update" &&
      event.assistantMessageEvent.type === "text_delta"
    ) {
      current += event.assistantMessageEvent.delta;
      onUpdate?.(current);
    }
  });

  return {
    getText: () => current.trim() || getLastAssistantText(session),
    unsubscribe,
  };
}

function buildSystemPrompt(
  parentSystemPrompt: string,
  cwd: string,
  readOnly: boolean,
): string {
  return `${parentSystemPrompt}

<subagent_context>
You are a general-purpose subagent running in an isolated in-memory session.
Your job is to complete the delegated task autonomously, then return a concise final result.

Operational rules:
- Use only the tools available in this subagent session.
- Use absolute file paths in file references when practical.
- Be concise but complete in your final answer.
- Do not ask the parent agent to do work you can do yourself.
- Do not call or simulate subagents recursively.
${readOnly ? "- This subagent is read-only: do not edit files or run mutating shell commands.\n" : ""}
Working directory: ${cwd}
</subagent_context>`;
}

async function runSubagent(
  pi: ExtensionAPI,
  ctx: ExtensionContext,
  id: string,
  prompt: string,
  abortSignal: AbortSignal,
  readOnly: boolean,
  onTextUpdate?: (text: string) => void,
  onSessionCreated?: (session: AgentSession) => void,
): Promise<{ session: AgentSession; result: string }> {
  const agentDir = getAgentDir();
  const loader = new DefaultResourceLoader({
    cwd: ctx.cwd,
    agentDir,
    noExtensions: true,
    noSkills: true,
    noPromptTemplates: true,
    noThemes: true,
    noContextFiles: true,
    systemPromptOverride: () =>
      buildSystemPrompt(ctx.getSystemPrompt(), ctx.cwd, readOnly),
    appendSystemPromptOverride: () => [],
  });
  await loader.reload();

  const { session } = await createAgentSession({
    cwd: ctx.cwd,
    agentDir,
    sessionManager: SessionManager.inMemory(ctx.cwd),
    settingsManager: SettingsManager.create(ctx.cwd, agentDir),
    modelRegistry: ctx.modelRegistry,
    model: ctx.model,
    thinkingLevel: pi.getThinkingLevel(),
    tools: readOnly ? ["read", "bash"] : SUBAGENT_TOOLS,
    resourceLoader: loader,
  });

  session.setSessionName(`subagent#${id}`);

  onSessionCreated?.(session);

  const collector = collectAssistantText(session, onTextUpdate);
  const abort = () => session.abort().catch(() => {});
  abortSignal.addEventListener("abort", abort, { once: true });

  try {
    if (abortSignal.aborted) {
      await session.abort().catch(() => {});
      throw new Error("Subagent stopped before it started.");
    }

    await session.prompt(prompt);
    return { session, result: collector.getText().trim() || "No output." };
  } finally {
    abortSignal.removeEventListener("abort", abort);
    collector.unsubscribe();
  }
}

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "spawn_subagent",
    label: "Spawn Subagent",
    description:
      "Run a delegated task in a separate general-purpose agent session. " +
      "Use this for self-contained investigation or implementation work that benefits from an isolated context. " +
      "Foreground mode returns the result inline; background mode returns an id and notifies when complete.",
    parameters: Type.Object({
      prompt: Type.String({
        description:
          "The complete task for the subagent to perform autonomously.",
      }),
      description: Type.Optional(
        Type.String({
          description: "Short description shown in status/result messages.",
        }),
      ),
      background: Type.Optional(
        Type.Boolean({
          description:
            "Run in background and return immediately. Default: false.",
        }),
      ),
      readOnly: Type.Optional(
        Type.Boolean({
          description:
            "When true, run the subagent with read and bash tools only, without file editing tools. Default: false.",
        }),
      ),
    }),
    async execute(_toolCallId, params, signal, onUpdate, ctx) {
      const id = makeId();
      const description = params.description?.trim() || "Subagent task";
      const abortController = new AbortController();
      const parentAbort = () => abortController.abort();
      const attachParentAbort = !params.background;
      if (attachParentAbort)
        signal?.addEventListener("abort", parentAbort, { once: true });

      const record: SubagentRecord = {
        id,
        description,
        status: "running",
        startedAt: Date.now(),
        promise: Promise.resolve(),
        abortController,
      };
      records.set(id, record);

      record.promise = (async () => {
        try {
          const { session, result } = await runSubagent(
            pi,
            ctx,
            id,
            params.prompt,
            abortController.signal,
            params.readOnly ?? false,
            params.background
              ? undefined
              : (text) =>
                  onUpdate?.(
                    textResult(
                      `Subagent ${id} running...\n\n${truncate(text, 1200)}`,
                      { id, status: "running" },
                    ),
                  ),
            (session) => {
              record.session = session;
            },
          );
          record.session = session;
          record.status = abortController.signal.aborted
            ? "stopped"
            : "completed";
          record.result = result;
          record.completedAt = Date.now();
        } catch (error) {
          record.status = abortController.signal.aborted ? "stopped" : "error";
          record.error = error instanceof Error ? error.message : String(error);
          record.completedAt = Date.now();
        } finally {
          record.session?.dispose?.();
          record.session = undefined;
          if (attachParentAbort)
            signal?.removeEventListener("abort", parentAbort);
        }
      })();

      if (params.background) {
        return textResult(
          `Subagent started in background.\nID: ${id}\nDescription: ${description}\n\nUse get_subagent_result with this ID to check status or retrieve the full result.`,
          { id, status: "running", background: true },
        );
      }

      await record.promise;
      const result =
        record.status === "completed"
          ? textResult(record.result ?? "No output.", {
              id,
              status: record.status,
            })
          : textResult(
              `Subagent ${record.status}: ${record.error ?? "stopped"}`,
              { id, status: record.status },
            );
      records.delete(id);
      return result;
    },
  });

  pi.registerTool({
    name: "get_subagent_result",
    label: "Get Subagent Result",
    description:
      "Check status and retrieve the result of a background subagent.",
    parameters: Type.Object({
      id: Type.String({
        description: "The subagent id returned by the subagent tool.",
      }),
      wait: Type.Optional(
        Type.Boolean({
          description: "Wait for completion before returning. Default: false.",
        }),
      ),
    }),
    async execute(_toolCallId, params) {
      const record = records.get(params.id);
      if (!record) return textResult(`Subagent not found: ${params.id}`);

      if (params.wait && record.status === "running") {
        await record.promise;
      }

      const durationMs = (record.completedAt ?? Date.now()) - record.startedAt;
      const header = `Subagent ${record.id} | ${record.status} | ${durationMs}ms\nDescription: ${record.description}\n`;

      if (record.status === "running") {
        return textResult(`${header}\nStill running.`);
      }
      if (record.status === "completed") {
        return textResult(`${header}\n${record.result ?? "No output."}`);
      }
      return textResult(`${header}\n${record.error ?? record.status}`);
    },
  });

  pi.registerTool({
    name: "stop_subagent",
    label: "Stop Subagent",
    description: "Stop a running background subagent by ID.",
    parameters: Type.Object({
      id: Type.String({
        description: "The subagent id returned by spawn_subagent.",
      }),
    }),
    async execute(_toolCallId, params) {
      const record = records.get(params.id);
      if (!record) return textResult(`Subagent not found: ${params.id}`);
      if (record.status !== "running") {
        return textResult(
          `Subagent ${record.id} is not running (status: ${record.status}).`,
          {
            id: record.id,
            status: record.status,
          },
        );
      }

      record.status = "stopped";
      record.completedAt = Date.now();
      record.abortController.abort();
      await record.session?.abort?.().catch(() => {});

      return textResult(`Stopped subagent ${record.id}.`, {
        id: record.id,
        status: record.status,
      });
    },
  });

  pi.registerTool({
    name: "list_subagents",
    label: "List Subagents",
    description:
      "List subagents created in this session with their current status and IDs.",
    parameters: Type.Object({}),
    async execute() {
      const list = [...records.values()].sort(
        (a, b) => b.startedAt - a.startedAt,
      );
      if (list.length === 0)
        return textResult("No subagents in this session.", { count: 0 });

      const lines = list.map((record) => {
        const durationMs =
          (record.completedAt ?? Date.now()) - record.startedAt;
        return `- ${record.id} | ${record.status} | ${durationMs}ms | ${record.description}`;
      });

      return textResult(`Subagents (${list.length}):\n${lines.join("\n")}`, {
        count: list.length,
      });
    },
  });

  pi.on("session_shutdown", async () => {
    for (const record of records.values()) {
      if (record.status === "running") {
        record.abortController.abort();
      }
      record.session?.dispose?.();
    }
    records.clear();
  });
}
