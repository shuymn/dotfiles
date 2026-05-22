import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { runCli, toCliExec } from "../lib/cli";
import { addOptions, cliTimeoutMs } from "../lib/tavily-cli";
import type { CitationFormat, ResearchProfile } from "./types";

const MAX_CONTEXT_CHARS = 80_000;
const SEARCH_TIMEOUT_MS = 120_000;
const RESEARCH_TIMEOUT_MS = 600_000;
const DEFAULT_EXTRACT_TIMEOUT_SECONDS = 60;
export type TvlySearchOptions = {
  query: string;
  depth: "ultra-fast" | "fast" | "basic" | "advanced";
  maxResults: number;
  topic?: "general" | "news" | "finance";
  includeDomains?: string[];
  timeRange?: "day" | "week" | "month" | "year";
};

export type TvlyExtractOptions = {
  urls: string[];
  query?: string;
  chunksPerSource?: number;
  extractDepth?: "basic" | "advanced";
  format?: "markdown" | "text";
  timeoutSeconds?: number;
};

export type TvlyResearchOptions = {
  task: string;
  model: "mini" | "pro" | "auto";
  citationFormat: CitationFormat;
  timeoutSeconds?: number;
};

export function profileDomains(profile: ResearchProfile): string[] | undefined {
  if (profile === "academic") {
    return [
      "arxiv.org",
      "semanticscholar.org",
      "openreview.net",
      "aclanthology.org",
      "paperswithcode.com",
    ];
  }
  if (profile === "technical") {
    return ["github.com", "developer.mozilla.org", "docs.github.com"];
  }
  return undefined;
}

export function buildSearchArgs(options: TvlySearchOptions): string[] {
  const args = ["search", options.query.trim(), "--json"];
  addOptions(args, [
    ["--depth", options.depth],
    ["--max-results", options.maxResults],
    ["--topic", options.topic],
    ["--time-range", options.timeRange],
    ["--include-domains", options.includeDomains],
  ]);
  return args;
}

export function buildExtractArgs(options: TvlyExtractOptions): string[] {
  const args = ["extract", ...options.urls, "--json"];
  addOptions(args, [
    ["--query", options.query],
    ["--chunks-per-source", options.chunksPerSource],
    ["--extract-depth", options.extractDepth],
    ["--format", options.format],
    ["--timeout", options.timeoutSeconds],
  ]);
  return args;
}

export function buildResearchRunArgs(options: TvlyResearchOptions): string[] {
  const args = ["research", "run", options.task.trim(), "--json"];
  addOptions(args, [
    ["--model", options.model],
    ["--citation-format", options.citationFormat],
    ["--timeout", options.timeoutSeconds],
  ]);
  return args;
}

async function runTvly(pi: ExtensionAPI, args: string[], signal?: AbortSignal) {
  return runCli(toCliExec(pi), {
    command: "tvly",
    args,
    timeout: args[0] === "research" ? RESEARCH_TIMEOUT_MS : SEARCH_TIMEOUT_MS,
    signal,
    parseJson: true,
    maxOutputChars: MAX_CONTEXT_CHARS,
    successLabel: "Tavily result",
    failureLabel: "Tavily command failed",
    truncationLabel: "research extension",
    failureHint:
      "Failed to execute tvly. Ensure the Tavily CLI is installed and authenticated (tvly auth).",
  });
}

export async function tvlySearch(
  pi: ExtensionAPI,
  options: TvlySearchOptions,
  signal?: AbortSignal,
) {
  return runTvly(pi, buildSearchArgs(options), signal);
}

export async function tvlyExtract(
  pi: ExtensionAPI,
  options: TvlyExtractOptions,
  signal?: AbortSignal,
) {
  return runCli(toCliExec(pi), {
    command: "tvly",
    args: buildExtractArgs(options),
    timeout: cliTimeoutMs(
      options.timeoutSeconds,
      DEFAULT_EXTRACT_TIMEOUT_SECONDS,
    ),
    signal,
    parseJson: true,
    maxOutputChars: MAX_CONTEXT_CHARS,
    successLabel: "Tavily result",
    failureLabel: "Tavily command failed",
    truncationLabel: "research extension",
    failureHint:
      "Failed to execute tvly. Ensure the Tavily CLI is installed and authenticated (tvly auth).",
  });
}

export async function tvlyResearchRun(
  pi: ExtensionAPI,
  options: TvlyResearchOptions,
  signal?: AbortSignal,
) {
  return runTvly(pi, buildResearchRunArgs(options), signal);
}
