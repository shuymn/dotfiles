import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { runCli, toCliExec } from "../lib/cli";
import type { CitationFormat, ResearchProfile } from "./types";

const MAX_CONTEXT_CHARS = 80_000;
const SEARCH_TIMEOUT_MS = 120_000;
const RESEARCH_TIMEOUT_MS = 600_000;
const DEFAULT_EXTRACT_TIMEOUT_SECONDS = 60;
const TOOL_TIMEOUT_GRACE_MS = 10_000;

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

function addOption(
  args: string[],
  flag: string,
  value: string | number | boolean | string[] | undefined,
) {
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

function cliTimeoutMs(
  timeoutSeconds: number | undefined,
  defaultSeconds: number,
) {
  return (timeoutSeconds ?? defaultSeconds) * 1000 + TOOL_TIMEOUT_GRACE_MS;
}

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
  addOption(args, "--depth", options.depth);
  addOption(args, "--max-results", options.maxResults);
  addOption(args, "--topic", options.topic);
  addOption(args, "--time-range", options.timeRange);
  addOption(args, "--include-domains", options.includeDomains);
  return args;
}

export function buildExtractArgs(options: TvlyExtractOptions): string[] {
  const args = ["extract", ...options.urls, "--json"];
  addOption(args, "--query", options.query);
  addOption(args, "--chunks-per-source", options.chunksPerSource);
  addOption(args, "--extract-depth", options.extractDepth);
  addOption(args, "--format", options.format);
  addOption(args, "--timeout", options.timeoutSeconds);
  return args;
}

export function buildResearchRunArgs(options: TvlyResearchOptions): string[] {
  const args = ["research", "run", options.task.trim(), "--json"];
  addOption(args, "--model", options.model);
  addOption(args, "--citation-format", options.citationFormat);
  addOption(args, "--timeout", options.timeoutSeconds);
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
