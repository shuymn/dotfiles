import { describe, expect, test } from "bun:test";
import { stripVTControlCharacters } from "node:util";
import type { WorkflowPhase } from "./phases";
import type { ActiveReviewRun } from "./workflow";
import { phaseLabel, renderReviewWidgetText } from "./view";

function phases(files: WorkflowPhase["file"][]): WorkflowPhase[] {
  return files.map((file) => ({ file, instructions: `${file} instructions` }));
}

function run(
  phaseFiles: WorkflowPhase["file"][],
  overrides: Partial<ActiveReviewRun> = {},
): ActiveReviewRun {
  return {
    id: "run-1",
    cwd: "/repo",
    targets: [{ path: "src/app.ts", status: "explicit", source: "explicit" }],
    diff: "",
    phases: phases(phaseFiles),
    noFix: false,
    instructions: "",
    nextPhaseIndex: 1,
    phaseOutputs: [],
    phaseInProgress: true,
    gapfillLoopCount: 0,
    ...overrides,
  };
}

describe("review widget view", () => {
  test("maps workflow phase files to human labels", () => {
    expect(phaseLabel("01-recon.md")).toBe("Recon");
    expect(phaseLabel("09-summary.md")).toBe("Summary");
  });

  test("renders current running phase above prior completed phases", () => {
    const lines = renderReviewWidgetText(
      run(["01-recon.md", "02-hunt.md", "03-validate.md"]),
      "running",
      2,
    );

    expect(lines).toEqual([
      "● Review 2/3 running",
      "├─ ✓ Recon",
      "└─ ◐ Hunt running",
    ]);
  });

  test("renders queued phase state", () => {
    const lines = renderReviewWidgetText(
      run(["01-recon.md", "02-hunt.md"]),
      "queued",
      2,
    );

    expect(lines).toEqual([
      "● Review 2/2 queued",
      "├─ ✓ Recon",
      "└─ ○ Hunt queued",
    ]);
  });

  test("renders gapfill hunt loop as a timeline step", () => {
    const lines = renderReviewWidgetText(
      run(
        [
          "01-recon.md",
          "02-hunt.md",
          "03-validate.md",
          "04-gapfill.md",
          "05-dedupe.md",
        ],
        {
          phaseOutputs: [
            { phaseIndex: 0, phaseFile: "01-recon.md", notes: "recon" },
            { phaseIndex: 1, phaseFile: "02-hunt.md", notes: "hunt" },
            { phaseIndex: 2, phaseFile: "03-validate.md", notes: "validate" },
            { phaseIndex: 3, phaseFile: "04-gapfill.md", notes: "gapfill" },
          ],
          gapfillLoopCount: 1,
        },
      ),
      "running",
      2,
    );

    expect(lines).toEqual([
      "● Review step 5 running",
      "├─ ✓ Recon",
      "├─ ✓ Hunt",
      "├─ ✓ Validate",
      "├─ ✓ Gapfill",
      "└─ ◐ Hunt #2 running",
    ]);
  });

  test("truncates and shows current phase with accurate overflow", () => {
    const lines = renderReviewWidgetText(
      run([
        "01-recon.md",
        "02-hunt.md",
        "03-validate.md",
        "04-gapfill.md",
        "05-dedupe.md",
        "06-trace.md",
        "07-fix.md",
        "08-verify.md",
        "09-summary.md",
      ]),
      "running",
      9,
      { width: 18, maxLines: 3 },
    );

    const plainLines = lines.map(stripVTControlCharacters);
    expect(plainLines.every((line) => line.length <= 18)).toBe(true);
    expect(plainLines).toEqual([
      "● Review 9/9 runni",
      "├─ +8 more",
      "└─ ◐ Summary runni",
    ]);
  });

  test("keeps current phase and overflow count with two max lines", () => {
    const lines = renderReviewWidgetText(
      run([
        "01-recon.md",
        "02-hunt.md",
        "03-validate.md",
        "04-gapfill.md",
        "05-dedupe.md",
        "06-trace.md",
        "07-fix.md",
        "08-verify.md",
        "09-summary.md",
      ]),
      "running",
      9,
      { maxLines: 2 },
    );

    expect(lines).toEqual([
      "● Review 9/9 running",
      "└─ ◐ Summary running (+8 more)",
    ]);
  });

  test("preserves header for one max line and honors zero max lines", () => {
    const active = run(["01-recon.md", "02-hunt.md"]);

    expect(renderReviewWidgetText(active, "running", 2, { maxLines: 1 })).toEqual([
      "● Review 2/2 running",
    ]);
    expect(renderReviewWidgetText(active, "running", 2, { maxLines: 0 })).toEqual(
      [],
    );
  });
});
