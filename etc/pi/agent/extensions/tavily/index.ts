import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { StringEnum } from "@earendil-works/pi-ai";
import { Type } from "typebox";

type JsonValue = unknown;

const SEARCH_DEPTHS = ["ultra-fast", "fast", "basic", "advanced"] as const;
const TOPICS = ["general", "news", "finance"] as const;
const TIME_RANGES = ["day", "week", "month", "year"] as const;
const EXTRACT_DEPTHS = ["basic", "advanced"] as const;
const CONTENT_FORMATS = ["markdown", "text"] as const;

const MAX_CONTEXT_CHARS = 60_000;
const SEARCH_TIMEOUT_MS = 120_000;
const AUTH_TIMEOUT_MS = 20_000;
const DEFAULT_EXTRACT_TIMEOUT_SECONDS = 60;
const DEFAULT_SITE_TIMEOUT_SECONDS = 150;
const TOOL_TIMEOUT_GRACE_MS = 10_000;

type OptionValue = string | number | boolean | string[] | undefined;

function addOption(args: string[], flag: string, value: OptionValue) {
  if (value === undefined || value === false) return;
  if (value === true) {
    args.push(flag);
    return;
  }
  const rendered = Array.isArray(value)
    ? value.filter(Boolean).join(",")
    : String(value);
  if (rendered.length > 0) args.push(flag, rendered);
}

function addOptions(
  args: string[],
  options: readonly (readonly [flag: string, value: OptionValue])[],
) {
  for (const [flag, value] of options) addOption(args, flag, value);
}

function parseJson(stdout: string): JsonValue | undefined {
  try {
    return JSON.parse(stdout);
  } catch {
    return undefined;
  }
}

function renderForModel(
  stdout: string,
  stderr: string,
  code: number,
  parsed: JsonValue | undefined,
) {
  const body =
    parsed === undefined ? stdout.trim() : JSON.stringify(parsed, null, 2);
  const prefix =
    code === 0
      ? "Tavily result:"
      : `Tavily command failed with exit code ${code}:`;
  const diagnostic = stderr.trim() ? `\n\nstderr:\n${stderr.trim()}` : "";
  const full = `${prefix}\n\n${body}${diagnostic}`.trim();
  if (full.length <= MAX_CONTEXT_CHARS) return full;
  return `${full.slice(0, MAX_CONTEXT_CHARS)}\n\n[truncated by tavily extension: ${full.length - MAX_CONTEXT_CHARS} chars omitted]`;
}

function errorFromToolText(text: string): Error {
  return new Error(text);
}

async function runTvly(
  pi: ExtensionAPI,
  commandArgs: string[],
  signal: AbortSignal | undefined,
  timeout: number,
) {
  try {
    const result = await pi.exec("tvly", commandArgs, { signal, timeout });
    const stdout = result.stdout ?? "";
    const parsed = parseJson(stdout);
    const text = renderForModel(
      stdout,
      result.stderr ?? "",
      result.code ?? 0,
      parsed,
    );
    if ((result.code ?? 0) !== 0) throw errorFromToolText(text);

    return {
      content: [{ type: "text" as const, text }],
      details: {
        command: ["tvly", ...commandArgs],
        exitCode: result.code,
        stdout: result.stdout,
        stderr: result.stderr,
        json: parsed,
      },
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(
      `Failed to execute tvly. Ensure the Tavily CLI is installed and authenticated (tvly auth).\n\n${message}`,
    );
  }
}

const searchSchema = Type.Object({
  query: Type.String({
    description:
      "Search query. Keep under 400 characters; use search-keyword style, not a long prompt.",
  }),
  depth: Type.Optional(
    StringEnum(SEARCH_DEPTHS, { description: "Search depth. Default: basic." }),
  ),
  maxResults: Type.Optional(
    Type.Integer({
      minimum: 0,
      maximum: 20,
      description: "Maximum results. Default: 5.",
    }),
  ),
  topic: Type.Optional(
    StringEnum(TOPICS, { description: "Search topic. Default: general." }),
  ),
  timeRange: Type.Optional(
    StringEnum(TIME_RANGES, { description: "Restrict recency." }),
  ),
  startDate: Type.Optional(
    Type.String({ description: "Results after date, YYYY-MM-DD." }),
  ),
  endDate: Type.Optional(
    Type.String({ description: "Results before date, YYYY-MM-DD." }),
  ),
  includeDomains: Type.Optional(
    Type.Array(Type.String(), {
      description: "Domains to include, e.g. ['sec.gov', 'reuters.com'].",
    }),
  ),
  excludeDomains: Type.Optional(
    Type.Array(Type.String(), { description: "Domains to exclude." }),
  ),
  country: Type.Optional(
    Type.String({ description: "Boost results from a country." }),
  ),
  includeAnswer: Type.Optional(
    StringEnum(["basic", "advanced"] as const, {
      description: "Include Tavily-generated answer.",
    }),
  ),
  includeRawContent: Type.Optional(
    StringEnum(CONTENT_FORMATS, {
      description:
        "Include full page content as markdown or text. Use sparingly.",
    }),
  ),
  includeImages: Type.Optional(
    Type.Boolean({ description: "Include image results." }),
  ),
  includeImageDescriptions: Type.Optional(
    Type.Boolean({ description: "Include AI image descriptions." }),
  ),
  chunksPerSource: Type.Optional(
    Type.Integer({
      minimum: 1,
      maximum: 5,
      description: "Chunks per source; requires fast/advanced depth.",
    }),
  ),
});

const extractSchema = Type.Object({
  urls: Type.Array(Type.String(), {
    minItems: 1,
    maxItems: 20,
    description: "URLs to extract. Maximum 20.",
  }),
  query: Type.Optional(
    Type.String({
      description: "Optional focus query to rerank chunks by relevance.",
    }),
  ),
  chunksPerSource: Type.Optional(
    Type.Integer({
      minimum: 1,
      maximum: 5,
      description: "Chunks per source. Requires query.",
    }),
  ),
  extractDepth: Type.Optional(
    StringEnum(EXTRACT_DEPTHS, {
      description: "Extraction depth. Use advanced for JS-heavy pages.",
    }),
  ),
  format: Type.Optional(
    StringEnum(CONTENT_FORMATS, {
      description: "Output content format. Default: markdown.",
    }),
  ),
  includeImages: Type.Optional(
    Type.Boolean({ description: "Include image URLs." }),
  ),
  timeoutSeconds: Type.Optional(
    Type.Integer({
      minimum: 1,
      maximum: DEFAULT_EXTRACT_TIMEOUT_SECONDS,
      description: "Tavily extraction timeout in seconds.",
    }),
  ),
});

const mapSchema = Type.Object({
  url: Type.String({ description: "Site URL to map." }),
  maxDepth: Type.Optional(Type.Integer({ minimum: 1, maximum: 5 })),
  maxBreadth: Type.Optional(Type.Integer({ minimum: 1 })),
  limit: Type.Optional(
    Type.Integer({
      minimum: 1,
      description: "Maximum URLs to discover. Default: 50.",
    }),
  ),
  instructions: Type.Optional(
    Type.String({
      description: "Natural-language guidance for URL discovery.",
    }),
  ),
  selectPaths: Type.Optional(
    Type.Array(Type.String(), {
      description: "Regex path patterns to include.",
    }),
  ),
  excludePaths: Type.Optional(
    Type.Array(Type.String(), {
      description: "Regex path patterns to exclude.",
    }),
  ),
  allowExternal: Type.Optional(
    Type.Boolean({ description: "Include external links." }),
  ),
  timeoutSeconds: Type.Optional(
    Type.Integer({ minimum: 10, maximum: DEFAULT_SITE_TIMEOUT_SECONDS }),
  ),
});

const crawlSchema = Type.Object({
  url: Type.String({ description: "Site URL to crawl." }),
  maxDepth: Type.Optional(
    Type.Integer({
      minimum: 1,
      maximum: 5,
      description: "Levels deep. Default: 1.",
    }),
  ),
  maxBreadth: Type.Optional(
    Type.Integer({ minimum: 1, description: "Links per page. Default: 20." }),
  ),
  limit: Type.Optional(
    Type.Integer({ minimum: 1, description: "Total pages cap. Default: 50." }),
  ),
  instructions: Type.Optional(
    Type.String({
      description:
        "Semantic focus for crawl. Prefer this for targeted docs/content.",
    }),
  ),
  chunksPerSource: Type.Optional(
    Type.Integer({
      minimum: 1,
      maximum: 5,
      description: "Chunks per page; requires instructions.",
    }),
  ),
  extractDepth: Type.Optional(StringEnum(EXTRACT_DEPTHS)),
  format: Type.Optional(StringEnum(CONTENT_FORMATS)),
  selectPaths: Type.Optional(
    Type.Array(Type.String(), {
      description: "Regex path patterns to include.",
    }),
  ),
  excludePaths: Type.Optional(
    Type.Array(Type.String(), {
      description: "Regex path patterns to exclude.",
    }),
  ),
  selectDomains: Type.Optional(
    Type.Array(Type.String(), {
      description: "Regex domain patterns to include.",
    }),
  ),
  excludeDomains: Type.Optional(
    Type.Array(Type.String(), {
      description: "Regex domain patterns to exclude.",
    }),
  ),
  allowExternal: Type.Optional(
    Type.Boolean({
      description: "Include external links. CLI default is true.",
    }),
  ),
  includeImages: Type.Optional(
    Type.Boolean({ description: "Include images." }),
  ),
  timeoutSeconds: Type.Optional(
    Type.Integer({ minimum: 10, maximum: DEFAULT_SITE_TIMEOUT_SECONDS }),
  ),
});

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "tavily_search",
    label: "Tavily Search",
    description:
      "Search the web with LLM-optimized Tavily results via the tvly CLI.",
    promptSnippet:
      "Search the web for current information, sources, news, or pages to inspect.",
    promptGuidelines: [
      "Use tavily_search when the user asks for current web information, recent news, source discovery, or external facts not available in the repository.",
      "Keep tavily_search queries under 400 characters; split complex prompts into focused sub-queries.",
      "Prefer tavily_search before tavily_extract when you do not already know the target URL.",
    ],
    parameters: searchSchema,
    async execute(_toolCallId, params, signal, onUpdate) {
      const query = params.query.trim();
      if (query.length > 400) {
        throw new Error(
          "tavily_search query must be 400 characters or fewer. Split complex questions into focused sub-queries.",
        );
      }
      const args = ["search", query, "--json"];
      addOptions(args, [
        ["--depth", params.depth],
        ["--max-results", params.maxResults],
        ["--topic", params.topic],
        ["--time-range", params.timeRange],
        ["--start-date", params.startDate],
        ["--end-date", params.endDate],
        ["--include-domains", params.includeDomains],
        ["--exclude-domains", params.excludeDomains],
        ["--country", params.country],
        ["--include-answer", params.includeAnswer],
        ["--include-raw-content", params.includeRawContent],
        ["--include-images", params.includeImages],
        ["--include-image-descriptions", params.includeImageDescriptions],
        ["--chunks-per-source", params.chunksPerSource],
      ]);
      onUpdate?.({
        content: [
          {
            type: "text",
            text: `Running tvly ${args.slice(0, 2).join(" ")} ...`,
          },
        ],
      });
      return runTvly(pi, args, signal, SEARCH_TIMEOUT_MS);
    },
  });

  pi.registerTool({
    name: "tavily_extract",
    label: "Tavily Extract",
    description:
      "Extract clean markdown/text content from one or more known URLs via the tvly CLI.",
    promptSnippet:
      "Extract readable content from specific URLs, including JS-rendered pages with advanced depth.",
    promptGuidelines: [
      "Use tavily_extract when you already have specific URLs and need page content, quotations, or details beyond search snippets.",
      "Use tavily_extract query and chunksPerSource to target a specific part of long pages.",
    ],
    parameters: extractSchema,
    async execute(_toolCallId, params, signal, onUpdate) {
      if (params.chunksPerSource !== undefined && !params.query) {
        throw new Error("tavily_extract chunksPerSource requires a query.");
      }
      const args = ["extract", ...params.urls, "--json"];
      addOptions(args, [
        ["--query", params.query],
        ["--chunks-per-source", params.chunksPerSource],
        ["--extract-depth", params.extractDepth],
        ["--format", params.format],
        ["--include-images", params.includeImages],
        ["--timeout", params.timeoutSeconds],
      ]);
      onUpdate?.({
        content: [
          {
            type: "text",
            text: `Extracting ${params.urls.length} URL(s) with Tavily...`,
          },
        ],
      });
      return runTvly(
        pi,
        args,
        signal,
        (params.timeoutSeconds ?? DEFAULT_EXTRACT_TIMEOUT_SECONDS) * 1000 +
          TOOL_TIMEOUT_GRACE_MS,
      );
    },
  });

  pi.registerTool({
    name: "tavily_map",
    label: "Tavily Map",
    description:
      "Discover URLs on a website without extracting page content via the tvly CLI.",
    promptSnippet:
      "Map a website to discover relevant URLs before extracting or crawling.",
    promptGuidelines: [
      "Use tavily_map when you need URL discovery for a site; it is faster than crawl and does not extract content.",
      "Prefer tavily_map then tavily_extract when only a few discovered pages are needed.",
    ],
    parameters: mapSchema,
    async execute(_toolCallId, params, signal, onUpdate) {
      const args = ["map", params.url, "--json"];
      addOptions(args, [
        ["--max-depth", params.maxDepth],
        ["--max-breadth", params.maxBreadth],
        ["--limit", params.limit],
        ["--instructions", params.instructions],
        ["--select-paths", params.selectPaths],
        ["--exclude-paths", params.excludePaths],
        ["--allow-external", params.allowExternal],
        ["--timeout", params.timeoutSeconds],
      ]);
      onUpdate?.({
        content: [
          { type: "text", text: `Mapping ${params.url} with Tavily...` },
        ],
      });
      return runTvly(
        pi,
        args,
        signal,
        (params.timeoutSeconds ?? DEFAULT_SITE_TIMEOUT_SECONDS) * 1000 +
          TOOL_TIMEOUT_GRACE_MS,
      );
    },
  });

  pi.registerTool({
    name: "tavily_crawl",
    label: "Tavily Crawl",
    description:
      "Crawl a website and extract content from multiple pages via the tvly CLI.",
    promptSnippet:
      "Crawl site sections for bulk content extraction with depth, breadth, path, and semantic filters.",
    promptGuidelines: [
      "Use tavily_crawl for bulk extraction from a site section; use tavily_map first if you only need URL discovery.",
      "Constrain tavily_crawl with instructions, selectPaths, excludePaths, maxDepth, and limit to avoid noisy or oversized results.",
    ],
    parameters: crawlSchema,
    async execute(_toolCallId, params, signal, onUpdate) {
      if (params.chunksPerSource !== undefined && !params.instructions) {
        throw new Error("tavily_crawl chunksPerSource requires instructions.");
      }
      const args = ["crawl", params.url, "--json"];
      addOptions(args, [
        ["--max-depth", params.maxDepth],
        ["--max-breadth", params.maxBreadth],
        ["--limit", params.limit],
        ["--instructions", params.instructions],
        ["--chunks-per-source", params.chunksPerSource],
        ["--extract-depth", params.extractDepth],
        ["--format", params.format],
        ["--select-paths", params.selectPaths],
        ["--exclude-paths", params.excludePaths],
        ["--select-domains", params.selectDomains],
        ["--exclude-domains", params.excludeDomains],
        ["--allow-external", params.allowExternal],
        ["--include-images", params.includeImages],
        ["--timeout", params.timeoutSeconds],
      ]);
      onUpdate?.({
        content: [
          { type: "text", text: `Crawling ${params.url} with Tavily...` },
        ],
      });
      return runTvly(
        pi,
        args,
        signal,
        (params.timeoutSeconds ?? DEFAULT_SITE_TIMEOUT_SECONDS) * 1000 +
          TOOL_TIMEOUT_GRACE_MS,
      );
    },
  });

  pi.registerTool({
    name: "tavily_auth_status",
    label: "Tavily Auth Status",
    description: "Check whether the tvly CLI is installed and authenticated.",
    promptSnippet:
      "Check Tavily CLI installation/authentication status when Tavily tools fail.",
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, signal) {
      return runTvly(pi, ["auth", "--json"], signal, AUTH_TIMEOUT_MS);
    },
  });
}
