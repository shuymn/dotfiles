import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";

import {
  profileDomains,
  tvlyExtract,
  tvlyResearchRun,
  tvlySearch,
} from "./cli";
import { planResearchQueries } from "./prompts";
import type {
  DeepResearchParams,
  DeepResearchResult,
  NormalizedResearchOptions,
  ResearchSource,
  ResearchTrace,
  ToolUpdateHandler,
} from "./types";

const DEFAULT_MAX_SOURCES = 8;
const MAX_MAX_SOURCES = 20;

function sendStatus(onUpdate: ToolUpdateHandler, text: string) {
  onUpdate?.({ content: [{ type: "text", text }], details: {} });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function findResultItems(json: unknown): unknown[] {
  if (!isRecord(json)) return [];
  if (Array.isArray(json.results)) return json.results;
  if (isRecord(json.data) && Array.isArray(json.data.results)) {
    return json.data.results;
  }
  return [];
}

function stringField(
  record: Record<string, unknown>,
  keys: string[],
): string | undefined {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return undefined;
}

function normalizeSource(item: unknown): ResearchSource | undefined {
  if (!isRecord(item)) return undefined;
  const url = stringField(item, ["url", "link", "href"]);
  if (!url) return undefined;
  return {
    url,
    title: stringField(item, ["title", "name"]),
    snippet: stringField(item, ["content", "snippet", "description"]),
    extracted: false,
  };
}

function normalizeUrl(url: string): string {
  try {
    const parsed = new URL(url);
    parsed.hash = "";
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return url.trim().replace(/\/$/, "");
  }
}

export function dedupeAndCapSources(
  sources: ResearchSource[],
  maxSources: number,
): ResearchSource[] {
  const seen = new Set<string>();
  const deduped: ResearchSource[] = [];
  for (const source of sources) {
    const key = normalizeUrl(source.url);
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(source);
    if (deduped.length >= maxSources) break;
  }
  return deduped;
}

export function normalizeResearchOptions(
  params: DeepResearchParams,
): NormalizedResearchOptions {
  const task = params.task.trim();
  if (!task) throw new Error("deep_research task is required.");

  return {
    task,
    depth: params.depth ?? "standard",
    profile: params.profile ?? "general",
    outputFormat: params.outputFormat ?? "brief",
    allowTavilyResearch: params.allowTavilyResearch ?? false,
    citationFormat: params.citationFormat ?? "numbered",
    maxSources: Math.min(
      Math.max(params.maxSources ?? DEFAULT_MAX_SOURCES, 1),
      MAX_MAX_SOURCES,
    ),
  };
}

function extractContent(json: unknown, url: string): string | undefined {
  const items = findResultItems(json);
  const item = items.find(
    (candidate) =>
      isRecord(candidate) && stringField(candidate, ["url", "link"]) === url,
  );
  if (isRecord(item))
    return stringField(item, ["raw_content", "content", "text"]);
  if (isRecord(json))
    return stringField(json, ["raw_content", "content", "text"]);
  return undefined;
}

function requiredSections(options: NormalizedResearchOptions): string[] {
  const sections = [
    "Executive Summary",
    "Key Findings",
    "Evidence Table",
    "Landscape / Taxonomy",
    "Disagreements or Uncertainties",
    "Recommended Next Steps",
    "Sources",
    "Search Trace",
  ];
  if (options.profile === "academic") {
    sections.splice(6, 0, "Related Papers", "Reading Order", "Research Gaps");
  }
  if (options.outputFormat === "comparison") {
    sections.splice(3, 0, "Options Compared", "Trade-offs", "Recommendation");
  }
  return sections;
}

export function assembleMarkdownReport(
  options: NormalizedResearchOptions,
  trace: ResearchTrace,
): string {
  const sourceLines = trace.sources.length
    ? trace.sources
        .map(
          (source, index) =>
            `${index + 1}. ${source.title ? `${source.title} — ` : ""}${source.url}`,
        )
        .join("\n")
    : "No sources collected.";
  const evidenceRows = trace.sources.length
    ? trace.sources
        .map(
          (source, index) =>
            `| Source ${index + 1} may inform the task | ${source.snippet ?? source.content?.slice(0, 240) ?? "Inspect source for details."} | [${index + 1}](${source.url}) | Medium |`,
        )
        .join("\n")
    : "| Coverage is weak | No sources were collected | n/a | Low |";
  const traceLines = trace.queries
    .map((query, index) => `${index + 1}. ${query.query} — ${query.purpose}`)
    .join("\n");

  const sections = new Map<string, string>([
    [
      "Executive Summary",
      `This brief collects source evidence for: ${options.task}\n\nCoverage should be reviewed by the agent before making strong claims.`,
    ],
    [
      "Key Findings",
      trace.sources.length
        ? trace.sources
            .map(
              (source, index) =>
                `- Source ${index + 1}: ${source.title ?? source.url}`,
            )
            .join("\n")
        : "- Source coverage is weak.",
    ],
    [
      "Evidence Table",
      `| Claim | Evidence | Source | Confidence |\n|---|---|---|---|\n${evidenceRows}`,
    ],
    [
      "Options Compared",
      "Use the collected sources to compare the main options relevant to the task.",
    ],
    [
      "Trade-offs",
      "Trade-offs require synthesis by the agent from the evidence above.",
    ],
    [
      "Recommendation",
      "Recommendation should be derived from the user's priorities and evidence confidence.",
    ],
    [
      "Landscape / Taxonomy",
      "Initial landscape should be synthesized from source titles, snippets, and extracted content.",
    ],
    [
      "Disagreements or Uncertainties",
      trace.sources.length
        ? "Check extracted source content for contradictions, date sensitivity, and missing primary sources."
        : "Source coverage is insufficient; conclusions should be tentative.",
    ],
    [
      "Recommended Next Steps",
      "- Verify critical claims against primary sources.\n- Run follow-up searches for gaps or disputed claims.",
    ],
    [
      "Related Papers",
      "Academic source discovery is domain-biased in this MVP; native paper graph APIs are not included.",
    ],
    [
      "Reading Order",
      "Start with surveys/overviews, then primary papers, then critical or follow-up work.",
    ],
    [
      "Research Gaps",
      "Identify gaps after reviewing the collected papers and citation trail.",
    ],
    ["Sources", sourceLines],
    ["Search Trace", traceLines || "No searches executed."],
  ]);

  return [
    `# Research Brief`,
    ...requiredSections(options).map(
      (section) => `## ${section}\n\n${sections.get(section) ?? ""}`,
    ),
  ].join("\n\n");
}

async function maybeRunTavilyResearch(
  pi: ExtensionAPI,
  options: NormalizedResearchOptions,
  trace: ResearchTrace,
  signal: AbortSignal | undefined,
  ctx: ExtensionContext | undefined,
) {
  if (options.depth !== "deep") {
    trace.tavilyResearch = { used: false, skippedReason: "depth_not_deep" };
    return undefined;
  }

  let allowed = options.allowTavilyResearch;
  if (!allowed && ctx?.hasUI !== false && ctx?.ui?.confirm) {
    allowed = await ctx.ui.confirm(
      "Tavily Research の実行確認",
      "高コストな Tavily Research を実行しますか？（通常の search/extract 結果に追加します）",
    );
  }

  if (!allowed) {
    trace.tavilyResearch = {
      used: false,
      skippedReason:
        ctx?.hasUI === false
          ? "no_ui_confirmation_unavailable"
          : "not_approved",
    };
    return undefined;
  }

  const model = options.profile === "general" ? "auto" : "mini";
  const result = await tvlyResearchRun(
    pi,
    {
      task: options.task,
      model,
      citationFormat: options.citationFormat,
    },
    signal,
  );
  trace.tavilyResearch = { used: true, model };
  return result.json ?? result.stdout;
}

export async function runDeepResearch(
  pi: ExtensionAPI,
  params: DeepResearchParams,
  signal?: AbortSignal,
  onUpdate?: ToolUpdateHandler,
  ctx?: ExtensionContext,
): Promise<DeepResearchResult> {
  const options = normalizeResearchOptions(params);
  const queries = planResearchQueries(options);
  const trace: ResearchTrace = {
    task: options.task,
    depth: options.depth,
    profile: options.profile,
    queries,
    searches: [],
    sources: [],
  };

  sendStatus(
    onUpdate,
    `Tavily search を ${queries.length} 件実行しています...`,
  );
  const discovered: ResearchSource[] = [];
  for (const query of queries) {
    const result = await tvlySearch(
      pi,
      {
        query: query.query,
        depth: options.depth === "quick" ? "basic" : "fast",
        maxResults: options.depth === "quick" ? 3 : 5,
        topic: options.profile === "news" ? "news" : "general",
        timeRange: options.profile === "news" ? "month" : undefined,
        includeDomains: profileDomains(options.profile),
      },
      signal,
    );
    const items = findResultItems(result.json);
    trace.searches.push({ query: query.query, resultCount: items.length });
    discovered.push(
      ...items
        .map(normalizeSource)
        .filter((source): source is ResearchSource => Boolean(source)),
    );
  }

  trace.sources = dedupeAndCapSources(discovered, options.maxSources);

  if (trace.sources.length > 0) {
    sendStatus(
      onUpdate,
      `Tavily extract で ${trace.sources.length} 件を確認しています...`,
    );
    const extractResult = await tvlyExtract(
      pi,
      {
        urls: trace.sources.map((source) => source.url),
        query: options.task,
        chunksPerSource: 2,
        extractDepth: "basic",
        format: "markdown",
      },
      signal,
    );
    trace.sources = trace.sources.map((source) => ({
      ...source,
      extracted: true,
      content: extractContent(extractResult.json, source.url),
    }));
  }

  const tavilyResearchOutput = await maybeRunTavilyResearch(
    pi,
    options,
    trace,
    signal,
    ctx,
  );

  return {
    markdown: assembleMarkdownReport(options, trace),
    trace,
    tavilyResearchOutput,
  };
}

export function toolResult(result: DeepResearchResult) {
  return {
    content: [{ type: "text" as const, text: result.markdown }],
    details: {
      trace: result.trace,
      tavilyResearchOutput: result.tavilyResearchOutput,
    },
  };
}
