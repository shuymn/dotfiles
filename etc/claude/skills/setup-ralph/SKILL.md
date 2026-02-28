---
name: setup-ralph
description: Prepares .ralph/ runtime state from an approved and analyzed decompose-plan plan bundle. Fills prd.json from plan.md task mappings and updates prompt.md with project-specific context, rules, and quality gates. Use after plan approval, analyze-plan PASS, and ralph init.
argument-hint: "[plan-path]"
---

# Setup Ralph

Prepare `.ralph/` for the execution loop: fill `prd.json` from an approved plan bundle and update `prompt.md` with project-specific guidance.

Prerequisite: `.ralph/` has already been initialized via `ralph init`.

## When to Use

- You have an approved plan bundle from `decompose-plan`.
- `analyze-plan` has produced `...-plan.analysis.md` with PASS verdict.
- `.ralph/` already exists (created by `ralph init`).
- Input: a plan.md file path (passed as argument or resolved interactively) and its derived `...-plan.analysis.md`.
- Output: updated `.ralph/prd.json` and `.ralph/prompt.md`.

## <HARD-GATE: PLAN APPROVAL>

Do NOT sync a plan that has not been explicitly approved by the user.

- Verify the plan's `Checkpoint Summary` passes full validation (see Step 1.5).
- Verify the analysis report (`...-plan.analysis.md`) exists and has PASS verdicts (see Step 1.6).
- If any required key is missing or any verdict is not PASS, stop and ask the user to fix the plan first.

## Process

### Step 1: Resolve Plan Path

1. If `$ARGUMENTS` is provided, use it as the plan path directly.
2. If no argument, search `docs/plans/*-plan.md` for available plans.
3. If multiple plans exist, present the list and ask the user to select one.
4. If no plans exist, stop and inform the user.
5. Validate the resolved path exists and is a `decompose-plan` plan bundle:
   - The file contains `## Task Dependency Graph`.
   - The file contains `## Checkpoint Summary` with all required keys:
     - `Alignment Verdict: PASS`
     - `Forward Fidelity: PASS`
     - `Reverse Fidelity: PASS`
     - `Non-Goal Guard: PASS`
     - `Granularity Guard: PASS`
     - `Trace Pack` and `Compose Pack` paths that match the plan header links
     - `Updated At`
6. Validate analysis report readiness:
   - Derive analysis path by replacing `-plan.md` with `-plan.analysis.md`.
   - The analysis file exists.
   - The analysis `## Summary` contains:
     - `Overall Verdict: PASS`
     - `Bundle Integrity: PASS`
     - `Traceability Integrity: PASS`
     - `Scope Integrity: PASS`
     - `Testability Integrity: PASS`
     - `Execution Readiness: PASS`
     - `Updated At`

### Step 2: Parse Plan Tasks

Extract tasks from the plan.md by parsing each `### Task N: <title>` section:

1. **Task ID**: Extract `N` from `### Task N:` and map to `task-N`.
2. **Title**: Extract the title text after `### Task N: `.
3. **Dependencies**: Parse `**Dependencies**: T1, T2` (or `none`).
   - Map `TN` references to `task-N` story IDs.
   - `none` maps to an empty array `[]`.
4. Validate the dependency graph:
   - All referenced dependency IDs exist as parsed tasks.
   - No circular dependencies.

### Step 3: Derive Metadata

1. **project**: Identify a short slug for the project. Use any reasonable source: git remote URL, directory name, `AGENTS.md` references, or the plan context. There is no strict format — pick what feels natural as a project identifier.
2. **branchName**: Read the plan's `**Goal**`, `**Architecture**`, `**Tech Stack**`, and task titles to understand the overall intent, then generate a branch name that concisely describes the change.
   - Format: `<type>/<slug>` (e.g., `feat/config-schema-sync`, `refactor/runner-error-handling`).
   - `<type>` is one of: `feat`, `fix`, `refactor`, `chore`, `docs` — choose based on the plan's primary intent.
   - `<slug>` is a short, descriptive kebab-case name (2-4 words) summarizing the plan scope. Use your judgement — do not mechanically extract from the filename or title.
   - The filename and heading are available as hints, but the branch name should reflect the plan's actual content.
3. If either value cannot be determined, ask the user.

### Step 4: Write prd.json

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
      "deps": ["task-0"],
      "passes": false
    }
  ]
}
```

Rules:
- All stories start with `"passes": false`.
- Story order matches task order in the plan.
- The `plan` field is the relative path from the project root.

### Step 5: Update prompt.md

Update the editable sections of `.ralph/prompt.md` with project-specific content derived from `AGENTS.md` (or `CLAUDE.md`) and the plan.

Read project guidance sources in order:
1. `AGENTS.md` at project root (if exists).
2. The resolved plan.md (for tech stack and verification commands).

Update only the following sections (preserve all other sections unchanged):

1. **Context**: Add project-specific context.
   - Repository structure and key directories from `AGENTS.md`.
   - Tech stack and architecture from the plan header (`**Architecture**`, `**Tech Stack**`).
   - Key packages and their responsibilities relevant to the plan scope.

2. **Rules**: Add project-specific coding rules.
   - Coding conventions from `AGENTS.md` (error handling, naming, testing style).
   - Plan-specific constraints (protected paths, file placement rules from task `**Files**` sections).
   - Add a rule directing the agent to use the `execute-plan` skill for each story during the Turn Procedure.

3. **Quality Gates**: Add project-specific verification commands.
   - Build/test/lint commands from `AGENTS.md` (e.g., `task test`, `task lint`, `task fmt`).
   - Plan-specific verification commands from task `**DoD**` sections (e.g., `rtk go test ./internal/config/...`).

Rules for editing prompt.md:
- Never modify sections marked `<!-- do not edit: ... -->`.
- Never modify Task Selection, Turn Procedure, Progress Format, Codebase Patterns, or Stop Condition sections.
- Keep additions concise; prefer referencing `AGENTS.md` over duplicating its content.

### Step 6: Report

1. Summarize `prd.json` updates without dumping full file content:
   - project, plan path, branchName
   - story count and task ID range (e.g., `task-1` to `task-8`)
2. Summarize `prompt.md` updates without dumping section content:
   - What changed in Context, Rules, and Quality Gates
   - Any commands or constraints added/updated
3. Summarize:
   - Number of stories synced.
   - Dependency chain (e.g., `T1 -> T2 -> T3 -> T4`).
   - Derived metadata (project, branchName).
4. Suggest the user review both files and start the ralph loop.

## Stop Conditions

Stop immediately and ask user guidance when:

- `.ralph/` does not exist (user should run `ralph init` first).
- `.ralph/prd.json` or `.ralph/prompt.md` does not exist.
- Plan path cannot be resolved or does not exist.
- Plan is missing `Checkpoint Summary`, missing required keys, or has any verdict that is not PASS.
- Analysis report is missing, malformed, or has any verdict that is not PASS.
- A dependency references a task ID that does not exist in the plan.
- Circular dependency detected.
- branchName cannot be derived and user does not provide it.
- Neither `AGENTS.md` nor `CLAUDE.md` exists at the project root (no source for project-specific guidance).

## Key Principles

- **Deterministic Mapping**: The same plan.md always produces the same prd.json stories (task mapping is purely structural).
- **Plan Fidelity**: prd.json is a direct projection of plan.md tasks; do not add, remove, or reorder stories.
- **Minimal Edit**: Update only Context, Rules, and Quality Gates in prompt.md; never touch ralph runtime machinery sections.
- **Fail-Fast Validation**: Validate the plan structure and dependencies before writing any files.
