export const DEPTHS = ["quick", "standard", "deep"] as const;
export const PROFILES = [
  "general",
  "academic",
  "technical",
  "market",
  "news",
] as const;
export const OUTPUT_FORMATS = [
  "brief",
  "report",
  "comparison",
  "source_map",
] as const;
export const CITATION_FORMATS = ["numbered", "mla", "apa", "chicago"] as const;

export type ResearchDepth = (typeof DEPTHS)[number];
export type ResearchProfile = (typeof PROFILES)[number];
export type ResearchOutputFormat = (typeof OUTPUT_FORMATS)[number];
export type CitationFormat = (typeof CITATION_FORMATS)[number];

export type DeepResearchParams = {
  task: string;
  depth?: ResearchDepth;
  profile?: ResearchProfile;
  outputFormat?: ResearchOutputFormat;
  allowTavilyResearch?: boolean;
  citationFormat?: CitationFormat;
  maxSources?: number;
};

export type NormalizedResearchOptions = {
  task: string;
  depth: ResearchDepth;
  profile: ResearchProfile;
  outputFormat: ResearchOutputFormat;
  allowTavilyResearch: boolean;
  citationFormat: CitationFormat;
  maxSources: number;
};

export type PlannedQuery = {
  query: string;
  purpose: string;
};

export type ResearchSource = {
  url: string;
  title?: string;
  snippet?: string;
  extracted?: boolean;
  sourceType?: string;
  content?: string;
};

export type ResearchTrace = {
  task: string;
  depth: ResearchDepth;
  profile: ResearchProfile;
  queries: PlannedQuery[];
  searches: Array<{ query: string; resultCount: number }>;
  sources: ResearchSource[];
  tavilyResearch?: {
    used: boolean;
    model?: "mini" | "pro" | "auto";
    requestId?: string;
    skippedReason?: string;
  };
};

export type DeepResearchResult = {
  markdown: string;
  trace: ResearchTrace;
  tavilyResearchOutput?: unknown;
};

export type ResearchPhaseOutput = {
  phaseIndex: number;
  phaseFile: string;
  notes: string;
};

export type ResearchRunSeed = {
  id: string;
  cwd: string;
  options: NormalizedResearchOptions;
  phases: import("./phases").ResearchPhase[];
  instructions: string;
};

export type ActiveResearchRun = ResearchRunSeed & {
  nextPhaseIndex: number;
  phaseOutputs: ResearchPhaseOutput[];
  phaseInProgress: boolean;
  collectLoopCount: number;
};

export type ToolUpdateHandler =
  | ((update: {
      content: Array<{ type: "text"; text: string }>;
      details: Record<string, unknown>;
    }) => void)
  | undefined;
