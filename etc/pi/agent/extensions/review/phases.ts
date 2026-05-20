import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const WORKFLOW_DIR = "review-workflow";

export const WORKFLOW_PHASE_FILES = [
  "01-recon.md",
  "02-hunt.md",
  "03-validate.md",
  "04-gapfill.md",
  "05-dedupe.md",
  "06-trace.md",
  "07-fix.md",
  "08-verify.md",
  "09-summary.md",
] as const;

export type WorkflowPhaseFile = (typeof WORKFLOW_PHASE_FILES)[number];

export const HUNT_PHASE_FILE = "02-hunt.md" satisfies WorkflowPhaseFile;
export const GAPFILL_PHASE_FILE = "04-gapfill.md" satisfies WorkflowPhaseFile;
export const DEDUPE_PHASE_FILE = "05-dedupe.md" satisfies WorkflowPhaseFile;
export const FIX_PHASE_FILE = "07-fix.md" satisfies WorkflowPhaseFile;
export const VERIFY_PHASE_FILE = "08-verify.md" satisfies WorkflowPhaseFile;
export const SUMMARY_PHASE_FILE = "09-summary.md" satisfies WorkflowPhaseFile;

export const READ_ONLY_PHASE_FILES = new Set<WorkflowPhaseFile>([
  "01-recon.md",
  HUNT_PHASE_FILE,
  "03-validate.md",
  GAPFILL_PHASE_FILE,
  DEDUPE_PHASE_FILE,
  "06-trace.md",
  SUMMARY_PHASE_FILE,
]);

export const NO_FIX_SKIPPED_PHASE_FILES = new Set<WorkflowPhaseFile>([
  FIX_PHASE_FILE,
  VERIFY_PHASE_FILE,
]);

export type WorkflowPhase = {
  file: WorkflowPhaseFile;
  instructions: string;
};

export function phaseFilesForMode(noFix: boolean): WorkflowPhaseFile[] {
  return noFix
    ? WORKFLOW_PHASE_FILES.filter(
        (file) => !NO_FIX_SKIPPED_PHASE_FILES.has(file),
      )
    : [...WORKFLOW_PHASE_FILES];
}

export function isReadOnlyPhaseFile(file: WorkflowPhaseFile): boolean {
  return READ_ONLY_PHASE_FILES.has(file);
}

export async function loadWorkflowPhases(
  noFix: boolean,
): Promise<WorkflowPhase[]> {
  const extensionDir = dirname(fileURLToPath(import.meta.url));

  return Promise.all(
    phaseFilesForMode(noFix).map(async (file) => ({
      file,
      instructions: (
        await readFile(join(extensionDir, WORKFLOW_DIR, file), "utf8")
      ).trim(),
    })),
  );
}
