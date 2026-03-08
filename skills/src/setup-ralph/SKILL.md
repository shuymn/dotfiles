---
name: setup-ralph
description: Prepares .ralph/ runtime state from an approved and reviewed plan bundle. Syncs plan tasks into prd.json and updates prompt.run.md with project-specific context and quality gates. Use after plan approval, decompose-plan review PASS, and ralph init.
argument-hint: "[plan-path]"
---

## Path Resolution

- `<skill-root>` means the directory containing this `SKILL.md`.
- Resolve `scripts/...` and `references/...` relative to `<skill-root>`, not the caller's current working directory.

# Setup Ralph

Prepare `.ralph/` for the execution loop: fill `prd.json` from an approved plan bundle and update `prompt.run.md` with project-specific guidance.

Prerequisite: `.ralph/` has already been initialized via `ralph init`.

## Hard Gate

Do NOT sync a plan that has not been explicitly approved by the user.

## Process

### Step 1: Resolve and Validate the Plan Bundle

1. Resolve the target `plan.md` path from `$ARGUMENTS` or `docs/plans/*/plan.md`.
2. Validate the plan bundle with `skit bundle-validate-check <plan-file>`.
3. Confirm `Checkpoint Summary` contains:
   - `Alignment Verdict: PASS`
   - `Scope Contract Guard: PASS`
   - `Quality Gate Guard: PASS`
   - `Review Artifact`
   - `Trace Pack`
   - `Compose Pack`
   - `Updated At`
4. Derive `plan.review.md` from `Review Artifact` or the plan location.
5. Run `skit gate-check <review-file> <plan-file>`.
6. Require the final review artifact to show:
   - `Overall Verdict: PASS`
   - `Task Shape Blockers: none`
   - `Scope: PASS`
   - `Execution Readiness: PASS`

### Step 2: Parse Plan Tasks

Extract each `### Task N: <title>` section and sync it to one Ralph story.

Required story metadata:

- `id`: `task-N`
- `title`
- `deps`
- `passes`: `false`
- `risk_tier`
- `scope_contract`
- `boundary_required`
- `completion_gate`

Rules:

- `scope_contract` must preserve `Owned Paths`, `Shared Touchpoints`, and `Prohibited Paths`.
- `boundary_required` is true when the task declares `Boundary Verification`.
- `completion_gate` is true when the plan as a whole requires `completion-audit`, or when the task belongs to a public/runtime/release-claim path that cannot be closed by local task PASS alone.

### Step 3: Write `.ralph/prd.json`

Overwrite `.ralph/prd.json` with:

```json
{
  "project": "<derived-project-slug>",
  "plan": "<relative-path-to-plan.md>",
  "branchName": "<derived-branch-name>",
  "stories": [
    {
      "id": "task-1",
      "title": "<task title>",
      "deps": [],
      "passes": false,
      "risk_tier": "Standard",
      "scope_contract": {
        "owned_paths": ["path/to/owned-area/**"],
        "shared_touchpoints": [
          {
            "path": "path/to/shared-file.ext",
            "rationale": "shared configuration or dependency update"
          }
        ],
        "prohibited_paths": ["path/to/prohibited-area/**"]
      },
      "boundary_required": false,
      "completion_gate": false
    }
  ]
}
```

### Step 4: Update `.ralph/prompt.run.md`

Update only the editable project-specific sections:

1. **Context**
   - repository structure
   - tech stack / architecture
   - plan-specific boundaries and packages
2. **Rules**
   - coding rules from `AGENTS.md`
   - `Scope Contract` handling guidance
   - requirement to use `execute-plan` for each story
   - requirement to run `completion-audit` when the plan or story metadata marks a completion gate
3. **Quality Gates**
   - project-wide `## Quality Gates`
   - any recurring boundary verification expectations that should be visible during the loop

### Step 5: Report

Summarize:

- project / plan / branchName
- number of synced stories
- dependency chain
- which story metadata fields were added or changed
- whether final `completion-audit` is required

## Stop Conditions

Stop and ask the user when:

- `.ralph/` does not exist
- `.ralph/prd.json` or `.ralph/prompt.run.md` does not exist
- the plan is missing `Checkpoint Summary` or required PASS guards
- `plan.review.md` is missing or not PASS
- `Task Shape Blockers` is not `none`
- task dependencies are invalid or cyclic
- no project guidance source (`AGENTS.md` or `CLAUDE.md`) exists

## Key Principles

- **Plan Fidelity**: `prd.json` is a projection of `plan.md`; do not invent or reorder stories.
- **Scope Fidelity**: preserve `Scope Contract` metadata; do not collapse it into flat file lists.
- **Completion Fidelity**: do not drop product-level closure requirements. If the plan needs `completion-audit`, keep that signal in Ralph state.
- **Minimal Edit**: update only the project-specific portions of `prompt.run.md`.
