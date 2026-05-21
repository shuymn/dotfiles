export const RESEARCH_PHASE_FILES = [
  "01-frame.md",
  "02-collect.md",
  "03-assess.md",
  "04-synthesize.md",
] as const;

export type ResearchPhaseFile = (typeof RESEARCH_PHASE_FILES)[number];

export const FRAME_PHASE_FILE = "01-frame.md" satisfies ResearchPhaseFile;
export const COLLECT_PHASE_FILE = "02-collect.md" satisfies ResearchPhaseFile;
export const ASSESS_PHASE_FILE = "03-assess.md" satisfies ResearchPhaseFile;
export const SYNTHESIZE_PHASE_FILE =
  "04-synthesize.md" satisfies ResearchPhaseFile;

export type ResearchPhase = {
  file: ResearchPhaseFile;
  label: string;
  instructions: string;
};

export const RESEARCH_PHASES: ResearchPhase[] = [
  {
    file: FRAME_PHASE_FILE,
    label: "Frame",
    instructions: `Frame the research before collecting sources.

Produce concise working notes with:
- research objective and success criteria
- assumptions and scope boundaries
- key research questions / angles to investigate
- likely source types and search strategy
- what would change the conclusion

Do not run Tavily yet unless the user already provided concrete URLs that must be inspected immediately.`,
  },
  {
    file: COLLECT_PHASE_FILE,
    label: "Collect",
    instructions: `Collect evidence for the framed questions.

Use Tavily search/extract/map/crawl directly as needed. Keep searches bounded and focused. Preserve source URLs, snippets, and why each source matters. For deep research escalation, use high-cost Tavily Research only when explicitly approved by the run options or user confirmation is already available.

Return a source/evidence table and a search trace. Do not write the final report yet.`,
  },
  {
    file: ASSESS_PHASE_FILE,
    label: "Assess",
    instructions: `Assess the collected evidence.

Judge source quality, contradictions, recency, bias, missing stakeholder perspectives, and whether the original questions are sufficiently answered. Identify material gaps that require another focused Collect pass.

If more collection is needed, emit focused follow-up queries in the required control block. Keep them narrow and decision-changing.`,
  },
  {
    file: SYNTHESIZE_PHASE_FILE,
    label: "Synthesize",
    instructions: `Write the final research brief.

Include executive summary, key findings, evidence table, landscape/taxonomy, disagreements or uncertainties, recommended next steps, sources, and search trace. Preserve citations/URLs and distinguish evidence from synthesis. Mention weak coverage explicitly.`,
  },
];
