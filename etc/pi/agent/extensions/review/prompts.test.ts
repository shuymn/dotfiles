import { describe, expect, test } from "bun:test";
import { phaseFilesForMode, type WorkflowPhase } from "./phases";
import {
  buildPhasePrompt,
  buildQuotedTargets,
  buildTargetList,
} from "./prompts";
import type { ActiveReviewRun } from "./workflow";

function phases(noFix = false): WorkflowPhase[] {
  return phaseFilesForMode(noFix).map((file) => ({
    file,
    instructions: `${file} instructions`,
  }));
}

function run(overrides: Partial<ActiveReviewRun> = {}): ActiveReviewRun {
  return {
    id: "run-1",
    cwd: "/repo",
    targets: [{ path: "src/app.ts", status: "explicit", source: "explicit" }],
    diff: "diff text",
    phases: phases(false),
    noFix: false,
    instructions: "",
    nextPhaseIndex: 1,
    phaseOutputs: [],
    phaseInProgress: true,
    gapfillLoopCount: 0,
    ...overrides,
  };
}

describe("review prompt rendering", () => {
  test("explicit file mode explains that git diff context is ignored", () => {
    const prompt = buildPhasePrompt(run({ diff: "ignored diff" }), 0);

    expect(prompt).toContain(
      "Explicit file mode: git diff is intentionally ignored",
    );
    expect(prompt).toContain(
      "Ignore repository git status/diffs for scope selection",
    );
  });

  test("noFix global rules prohibit edits", () => {
    const prompt = buildPhasePrompt(
      run({ noFix: true, phases: phases(true) }),
      0,
    );

    expect(prompt).toContain(
      "No-fix mode is enabled: do not edit files, run mutating commands, or apply fixes at any stage",
    );
  });

  test("additional user instructions are included after phase 1", () => {
    const prompt = buildPhasePrompt(
      run({ instructions: "focus on security regressions" }),
      1,
    );

    expect(prompt).toContain(
      "## Additional user instructions\n\nfocus on security regressions",
    );
  });

  test("previous phase outputs are embedded as untrusted context", () => {
    const prompt = buildPhasePrompt(
      run({
        phaseOutputs: [
          { phaseIndex: 0, phaseFile: "01-recon.md", notes: "recon notes" },
        ],
      }),
      1,
    );

    expect(prompt).toContain('<previous_phase_outputs untrusted="true">');
    expect(prompt).toContain(
      "Output #1 — Completed phase 1: 01-recon.md (occurrence 1)",
    );
    expect(prompt).toContain("recon notes");
  });

  test("previous phase output headings include chronological and occurrence labels", () => {
    const prompt = buildPhasePrompt(
      run({
        phaseOutputs: [
          { phaseIndex: 1, phaseFile: "02-hunt.md", notes: "first hunt" },
          { phaseIndex: 1, phaseFile: "02-hunt.md", notes: "second hunt" },
        ],
      }),
      4,
    );

    expect(prompt).toContain(
      "Output #1 — Completed phase 2: 02-hunt.md (occurrence 1)",
    );
    expect(prompt).toContain(
      "Output #2 — Completed phase 2: 02-hunt.md (occurrence 2)",
    );
  });

  test("only Gapfill phase includes the required control block", () => {
    const active = run();

    expect(buildPhasePrompt(active, 1)).not.toContain("<review_control>");
    expect(buildPhasePrompt(active, 3)).toContain("<review_control>");
    expect(buildPhasePrompt(active, 3)).toContain('{"new_hunt_tasks":[]}');
    expect(buildPhasePrompt(active, 3)).toContain(
      "Remaining Hunt loop budget after this Gapfill response: 2.",
    );
  });

  test("capped Gapfill prompt instructs an empty control task list", () => {
    const prompt = buildPhasePrompt(run({ gapfillLoopCount: 2 }), 3);

    expect(prompt).toContain("No Hunt loop budget remains");
    expect(prompt).toContain("Emit an empty new_hunt_tasks array");
  });

  test("only final phase includes final Japanese summary instruction", () => {
    const active = run();

    expect(buildPhasePrompt(active, 0)).toContain(
      "Do not summarize the whole workflow yet.",
    );
    expect(buildPhasePrompt(active, active.phases.length - 1)).toContain(
      "This is the final phase; provide the final Japanese summary.",
    );
  });

  test("formats target list and shell-quoted targets", () => {
    const targets: ActiveReviewRun["targets"] = [
      { path: "src/app.ts", status: "explicit", source: "explicit" },
      { path: "docs/read me.md", status: "M", source: "diff" },
    ];

    expect(buildTargetList(targets)).toContain('- "src/app.ts" (explicit)');
    expect(buildTargetList(targets)).toContain('- "docs/read me.md" (M; diff)');
    expect(buildQuotedTargets(targets)).toBe("'src/app.ts' 'docs/read me.md'");
  });
});
