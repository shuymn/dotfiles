import { StringEnum } from "@earendil-works/pi-ai";
import type {
  ExtensionAPI,
  ExtensionCommandContext,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

import { cliResultForTool } from "../lib/cli";
import { tvlyResearchRun } from "./cli";
import { RESEARCH_PHASES } from "./phases";
import { buildResearchPhasePrompt } from "./prompts";
import {
  type ActiveResearchRun,
  CITATION_FORMATS,
  DEPTHS,
  type DeepResearchParams,
  OUTPUT_FORMATS,
  PROFILES,
  type ResearchRunSeed,
} from "./types";
import { normalizeResearchOptions } from "./workflow";
import {
  type QueuedResearchPhase,
  ResearchWorkflowController,
} from "./workflow-controller";

const EMPTY_TASK_MESSAGE =
  "調査タスクを指定してください。例: /research React Server Components adoption risks in 2026";
const MAX_PHASE_NOTE_CHARS = 20_000;

const workflow = new ResearchWorkflowController();
let nextPhaseTimer: ReturnType<typeof setTimeout> | undefined;

const TAVILY_RESEARCH_MODELS = ["mini", "pro", "auto"] as const;

const deepResearchSchema = Type.Object({
  task: Type.String({
    description: "Research task or question to investigate.",
  }),
  depth: Type.Optional(
    StringEnum(DEPTHS, {
      description:
        "Research depth. Prefer quick or standard unless the user explicitly asks for deep/comprehensive research.",
    }),
  ),
  profile: Type.Optional(
    StringEnum(PROFILES, {
      description: "Source discovery and output bias. Defaults to general.",
    }),
  ),
  outputFormat: Type.Optional(
    StringEnum(OUTPUT_FORMATS, {
      description: "Preferred output shape. Defaults to brief.",
    }),
  ),
  allowTavilyResearch: Type.Optional(
    Type.Boolean({
      description:
        "Set true only when the user explicitly approved high-cost Tavily Research. Default false.",
    }),
  ),
  citationFormat: Type.Optional(
    StringEnum(CITATION_FORMATS, {
      description:
        "Citation format for Tavily Research escalation. Default numbered.",
    }),
  ),
  maxSources: Type.Optional(
    Type.Integer({
      minimum: 1,
      maximum: 20,
      description: "Maximum normalized sources to extract. Default 8.",
    }),
  ),
});

const tavilyResearchSchema = Type.Object({
  task: Type.String({
    description: "Research task to run through high-cost Tavily Research.",
  }),
  approved: Type.Boolean({
    description:
      "Must be true only when the user explicitly approved high-cost Tavily Research for this workflow.",
  }),
  model: Type.Optional(
    StringEnum(TAVILY_RESEARCH_MODELS, {
      description:
        "Tavily Research model. Use mini for narrow tasks, pro for broad multi-domain tasks, auto when unclear. Default auto.",
    }),
  ),
  citationFormat: Type.Optional(
    StringEnum(CITATION_FORMATS, {
      description: "Citation format. Default numbered.",
    }),
  ),
  timeoutSeconds: Type.Optional(
    Type.Integer({
      minimum: 1,
      maximum: 600,
      description: "Tavily Research timeout in seconds.",
    }),
  ),
});

function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return `${text.slice(0, maxChars)}\n\n[truncated: ${text.length - maxChars} chars omitted]`;
}

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

function getLatestAssistantMessageText(messages: unknown): string | undefined {
  try {
    return findLatestAssistantMessageText(messages);
  } catch {
    return undefined;
  }
}

function activeRun(): ActiveResearchRun | undefined {
  return workflow.getActiveRun();
}

function clearQueuedPhaseTimer(): void {
  if (!nextPhaseTimer) return;
  clearTimeout(nextPhaseTimer);
  nextPhaseTimer = undefined;
}

function clearActiveRun(): void {
  clearQueuedPhaseTimer();
  workflow.cancel();
}

function createResearchRun(
  cwd: string,
  params: DeepResearchParams,
  instructions = "",
): ResearchRunSeed {
  return {
    id: `${Date.now()}`,
    cwd,
    options: normalizeResearchOptions(params),
    phases: RESEARCH_PHASES,
    instructions,
  };
}

function sendQueuedPhase(pi: ExtensionAPI, queued: QueuedResearchPhase): void {
  pi.sendMessage(
    {
      customType: "research-command",
      content: buildResearchPhasePrompt(queued.run, queued.phaseIndex),
      display: false,
      details: {
        runId: queued.run.id,
        phase: queued.phase.file,
        phaseIndex: queued.phaseIndex + 1,
        phaseCount: queued.run.phases.length,
      },
    },
    { triggerTurn: true },
  );
}

function startResearchRun(
  pi: ExtensionAPI,
  run: ResearchRunSeed,
): ActiveResearchRun {
  const queued = workflow.start(run);
  try {
    sendQueuedPhase(pi, queued);
  } catch (error) {
    clearActiveRun();
    throw error;
  }
  return queued.run;
}

function queueNextPhaseAfterCurrentTurn(pi: ExtensionAPI, runId: string): void {
  clearQueuedPhaseTimer();
  nextPhaseTimer = setTimeout(() => {
    nextPhaseTimer = undefined;
    if (activeRun()?.id !== runId) return;
    const queued = workflow.startQueuedPhase();
    if (!queued) return;
    try {
      sendQueuedPhase(pi, queued);
    } catch {
      clearActiveRun();
    }
  }, 0);
}

export default function researchExtension(pi: ExtensionAPI) {
  pi.on("agent_end", async (event) => {
    if (!activeRun()?.phaseInProgress) return;

    const latestAssistantText = getLatestAssistantMessageText(event.messages);
    const decision = workflow.completePhase({
      latestAssistantText,
      truncateNotes: (text) => truncate(text, MAX_PHASE_NOTE_CHARS),
    });
    if (!decision) return;

    if (decision.kind === "completed") {
      clearQueuedPhaseTimer();
      return;
    }

    queueNextPhaseAfterCurrentTurn(pi, decision.run.id);
  });

  pi.on("session_shutdown", async () => {
    clearActiveRun();
  });

  pi.registerCommand("research", {
    description: "Run a multi-stage general deep research workflow for a task",
    handler: async (args: string, ctx: ExtensionCommandContext) => {
      await ctx.waitForIdle?.();

      const trimmedArgs = args.trim();
      if (trimmedArgs === "cancel" || trimmedArgs === "--cancel") {
        const runId = activeRun()?.id;
        clearActiveRun();
        ctx.ui.notify(
          runId
            ? `/research: ワークフロー ${runId} をキャンセルしました。`
            : "/research: キャンセルできるワークフローがありません。",
          "info",
        );
        return;
      }

      if (!trimmedArgs) {
        ctx.ui.notify(EMPTY_TASK_MESSAGE, "warning");
        return;
      }
      if (activeRun()) {
        ctx.ui.notify(
          "/research: 別のリサーチワークフローが既に実行中です。",
          "warning",
        );
        return;
      }

      try {
        const active = startResearchRun(
          pi,
          createResearchRun(ctx.cwd, { task: trimmedArgs }),
        );
        ctx.ui.notify(
          `/research: phase 1/${active.phases.length} をキューに追加しました。`,
          "info",
        );
      } catch (error) {
        ctx.ui.notify(
          `/research: ワークフローの phase をキューに追加できませんでした。${error instanceof Error ? ` ${error.message}` : ""}`,
          "error",
        );
      }
    },
  });

  pi.registerTool({
    name: "tavily_research",
    label: "Tavily Research",
    description:
      "Run high-cost Tavily Research via tvly research run. Use only when explicitly approved by the user or research workflow options.",
    promptSnippet:
      "Run Tavily Research only as an explicit high-cost escalation step inside a research workflow.",
    promptGuidelines: [
      "Use tavily_research only when the user explicitly approved high-cost Tavily Research or deep_research allowTavilyResearch is true.",
      "Prefer model mini for narrow tasks, auto when complexity is unclear, and pro only for broad multi-domain research or explicit user request.",
    ],
    parameters: tavilyResearchSchema,
    async execute(_toolCallId, params, signal) {
      if (!params.approved) {
        throw new Error(
          "tavily_research requires explicit user approval. Set approved=true only after the user approved high-cost Tavily Research.",
        );
      }
      const result = await tvlyResearchRun(
        pi,
        {
          task: params.task,
          model: params.model ?? "auto",
          citationFormat: params.citationFormat ?? "numbered",
          timeoutSeconds: params.timeoutSeconds,
        },
        signal,
      );
      return cliResultForTool(result);
    },
  });

  pi.registerTool({
    name: "deep_research",
    label: "Deep Research",
    description:
      "Queue a multi-stage research workflow that frames assumptions, collects sources, assesses evidence/gaps, and synthesizes a cited brief.",
    promptSnippet:
      "Use deep_research when the user asks for multi-source research, landscape mapping, comparisons, evidence-backed reports, or deep research.",
    promptGuidelines: [
      "Use deep_research when the user asks for multi-source research, landscape mapping, comparisons, evidence-backed reports, or deep research.",
      "Prefer quick or standard depth unless the user explicitly asks for deep/comprehensive research.",
      "Do not enable allowTavilyResearch unless the user explicitly approves high-cost Tavily Research or the command/user input made that approval clear.",
      "This tool queues a staged workflow; do not try to complete all research phases in the same assistant turn.",
    ],
    parameters: deepResearchSchema,
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      if (activeRun()) {
        return {
          content: [
            {
              type: "text" as const,
              text: "Another research workflow is already running.",
            },
          ],
          details: { activeRunId: activeRun()?.id },
        };
      }

      const run = createResearchRun(
        (ctx as ExtensionContext).cwd,
        params as DeepResearchParams,
      );
      let active: ActiveResearchRun;
      try {
        active = startResearchRun(pi, run);
      } catch (error) {
        return {
          content: [
            {
              type: "text" as const,
              text: `Failed to queue research workflow: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
          details: { status: "error" },
        };
      }
      return {
        content: [
          {
            type: "text" as const,
            text: `Queued research workflow ${active.id} phase 1/${active.phases.length} for: ${active.options.task}`,
          },
        ],
        details: {
          status: "queued",
          runId: active.id,
          phase: "01-frame.md",
          phaseIndex: 1,
          phaseCount: active.phases.length,
          options: active.options,
        },
      };
    },
  });
}
