---
name: decompose-plan
description: "Decomposes an approved design document into a TDD-based implementation plan or reviews an existing plan (mode=create|review). Create mode: task breakdown with traceability. Review mode: independent sub-agent verification absorbing the former analyze-plan audit. Use after design-doc approval when the user needs to break down a design into executable tasks, create an implementation plan, or generate a task list from a design."
allowed-tools: [Read, Write, Edit, Grep, Glob, TodoWrite, Bash]
---

## Path Resolution

- `<skill-root>` means the directory containing this `SKILL.md`.
- Resolve `scripts/...` and `references/...` relative to `<skill-root>`, not the caller's current working directory.
- When executing local helpers, use explicit paths such as `<skill-root>/scripts/...`.

## Mode Dispatch

Determine the execution mode from `$ARGUMENTS`:

- If the first whitespace-separated token of `$ARGUMENTS` is exactly `review`, or `$ARGUMENTS` contains `--review` or `mode=review` → **Review Mode**: read [references/review-mode.md](references/review-mode.md) and follow its instructions.
- Otherwise → **Create Mode** (default; continue to `# Task Decomposition from Design Doc`)

# Task Decomposition from Design Doc

Convert an approved design doc into a concise, execution-ready plan bundle.
Output instruction-level guidance only. Do not output implementation code snippets.

## Input / Output

- Input: a design doc in `docs/plans/<topic>/` (typically created by the `design-doc` skill).
  - If the design doc declares `Split Decision: root-sub`, treat the root doc plus all sub docs listed in its `Sub-Doc Index` as the design input set.
- Output is a 3-file bundle:
  - `docs/plans/<topic>/plan.md` (core, frequently read)
  - `docs/plans/<topic>/plan.trace.md` (traceability evidence, on-demand)
  - `docs/plans/<topic>/plan.compose.md` (reconstruction check, on-demand)

## <HARD-GATE>

Do NOT begin any implementation until the plan is explicitly approved by the user.
Reason: implementing against an unapproved plan locks in scope decisions the user hasn't seen yet; adjusting the plan before code is written is far cheaper than reverting code afterward.

No exceptions. Not even "just to test one thing" or "the first task is trivial."

## Create Mode Gate (Required before decomposition)

Before starting decomposition in create mode, verify the design review gate:

1. Run `<skill-root>/scripts/gate-check.sh <design.review.md> <design.md>`.
2. The review file must exist, contain `Overall Verdict: PASS`, and the Source Digest must match the current design file.
3. If the gate check fails, stop as `BLOCKED` and request the user to run `design-doc review` first.

## Split Fitness Gate

Before loading design atoms in create mode, verify that the source design's `single` / `root-sub` decision still holds:

1. Run `uv run --with pydantic python <skill-root>/scripts/split_check.py <design.md>`.
2. If the split check reports `FAIL`, stop as `BLOCKED` and request design updates before decomposition.
3. If the split check reports advisories only, continue, but keep `plan.md` compact and avoid compensating for a weak split with duplicated boundary-local narrative.

## Design Sufficiency Gate

Do not infer migration lifecycle details that are absent from the design doc.

- If the design includes breaking change, replacement, deprecation, migration, or compatibility staging:
  - Require `## Compatibility & Sunset` and `TEMPxx` enumeration in either:
    - `Temporary Mechanism Index` (preferred)
    - `Temporary Mechanism Ledger` (legacy-compatible)
  - Require in-doc closure summary for every `TEMPxx`:
    - `Sunset Closure Checklist` row (preferred)
    - legacy ledger row with equivalent closure fields (`Retirement Trigger`, `Retirement Verification`, `Removal Scope`; exact labels or unambiguous synonyms)
  - For every `TEMPxx`, require lifecycle closure fields:
    - Retirement Trigger
    - Retirement Verification
    - Removal Scope
  - Closure fields must be sourced from the in-doc checklist/ledger row; ADR `Sunset Clause` is supplemental and not a substitute for in-doc closure summary.
  - If lifecycle record points to ADR, require linked ADR `Sunset Clause` for that `TEMPxx`.
  - If any required lifecycle evidence is missing, stop as `BLOCKED` and request design completion before decomposition.
- Decomposition is allowed only when lifecycle closure is design-defined.

## Round-Trip Contract

Treat decomposition as a reversible transform.

- Forward: `Design Doc -(decompose)-> Tasks` must preserve all implementable intent.
- Reverse: `Tasks -(compose)-> Design Doc` must reconstruct the same scope and acceptance intent.
- Source of truth is always the design doc; tasks are a normalized executable view.
- If round-trip fidelity fails, revise tasks before presenting the plan.

## Plan Artifact Strategy

Keep the execution file thin and move heavy analysis to sidecars.

- `plan.md` must contain only what is needed repeatedly during implementation.
- `plan.trace.md` stores traceability and full check evidence.
- `plan.compose.md` stores reconstruction outputs and scope-diff evidence.
- Do not duplicate long sections across files. Use stable IDs and file links.

## Output Contract

### Core Plan (`plan.md`) Required Sections

1. Header (includes ## Quality Gates when detected)
2. Task Dependency Graph (compact form)
3. Task list (`Goal`, `RED`, `GREEN`, `REFACTOR`, `DoD`; no `TEMPxx`-specific fields)
4. Checkpoint Summary

### Trace Pack (`plan.trace.md`) Required Sections

1. Design Atom Index
2. Decision Trace (`DECxx -> ADR-xxxx`)
3. Design -> Task Trace Matrix
4. Task -> Design Compose Matrix
5. Temporary Mechanism Trace (`TEMPxx` lifecycle and closure status)
6. Behavioral Lock Map (`only/remove/no-fallback/fail-closed` requirements and their negative checks)
7. AC Ownership Map (`ACxx` -> Owner Task + Contributors)
8. Structural Self-Check evidence

### Compose Pack (`plan.compose.md`) Required Sections

1. Reconstructed design summary from tasks
2. Scope diff (`missing`, `extra`, `ambiguous`)
3. Alignment verdict and required fixes

### Link Contract (Required)

`plan.md` header must include:

- `**Trace Pack**: docs/plans/<topic>/plan.trace.md`
- `**Compose Pack**: docs/plans/<topic>/plan.compose.md`

### Markdown Rendering Rule (Required)

- Never rely on soft line breaks between consecutive key-value lines.
- Preferred format for key-value metadata blocks: `- **Key**: value`
- Alternative when many fields are present: markdown table

### Templates

- **Plan templates** (header, checkpoint summary, task structure): See [plan-templates.md](references/plan-templates.md)
- **Trace templates** (trace matrices, cross self-check, compose reconstruction): See [trace-templates.md](references/trace-templates.md)
- **Granularity poker rubric** (review-only scoring): See [granularity-poker.md](references/granularity-poker.md)

### Compression Rules

- Keep `plan.md` concise: no duplicated requirement prose, no full trace matrices, no long rationale blocks.
- Prefer stable IDs (`REQxx`, `ACxx`, `DECxx`) over repeated natural-language restatement.
- Put exhaustive mapping and diagnostics into sidecars.
- Keep each task minimal but executable; avoid narrative that does not change implementation behavior.
- If `plan.md` stops being a thin execution artifact because boundary-local explanations, repeated verification flows, or task narratives are spilling out of sidecars, re-run `uv run --with pydantic python <skill-root>/scripts/split_check.py <design-file>` and revisit the design split before finalizing.

### Strict Scope Rules

- Do not include code blocks for test or implementation in the plan bundle.
- Do not prescribe line-by-line implementation details.
- Do not add features outside the design doc.
- Keep each task outcome independently testable.
- Keep task granularity at one coherent, reviewable change unit; do not include commit commands or require commit execution.
- Do not use fixed file-count or LOC thresholds as hard rules.
- In create mode, do not score granularity or assign a granularity verdict.
- Ensure each task exposes the structural facts needed for review-mode scoring: one stated `Goal`, one main `RED` verification flow, explicit `Dependencies`, and a rollback boundary implied by `Files`/`Allowed Files`.

### Granularity Self-Check (Create Mode Only)

Use these non-scoring axes to shape tasks before presenting `plan.md`. Re-slice overloaded tasks, but do not assign cards, totals, thresholds, PASS/FAIL, or any granularity verdict in create mode; `decompose-plan review` remains the authoritative granularity gate.

- `Objective`: Keep each task to one stated objective. If a task contains multiple independently releasable outcomes, split them.
- `Surface`: Separate unrelated boundaries or top-level path families into different tasks.
- `Verification`: Keep one main verification flow in `RED`/`DoD`; move independent checks into follow-up tasks.
- `Rollback`: Separate reversible preparation from irreversible cutover or removal so rollback remains clear.

### Behavioral Lock Rules (Required)

For design atoms expressing hard behavioral constraints — restricting behavior to a single path, removing or replacing an existing capability, or mandating failure when a former path is attempted. Common keyword examples (not exhaustive): `only`, `must not`, `remove`, `retire`, `no fallback`, `fail-closed`, `唯一`, `廃止`, `禁止`:

- Add at least one executable negative check in RED or DoD proving the forbidden path fails.
- Add at least one executable positive check proving the new path works.
- For cross-boundary replacements (runtime path, transport, lifecycle), include at least one boundary-level command (integration/contract/CLI smoke), not package-local unit tests only.
- For legacy-key removals, include explicit rejection checks and an absence guard (no surviving legacy path).

## Process

### Step 1: Load Design Doc

1. Read the design doc specified by the user.
2. Detect decomposition strategy from `## Decomposition Strategy`:
   - If `Split Decision: single`, continue with the single design doc.
   - If `Split Decision: root-sub`, read all sub docs listed in `Sub-Doc Index`.
   - If `root-sub` is declared but `Sub-Doc Index` is missing or any listed sub doc is unreadable, stop as `BLOCKED`.
3. Read `Goals`, `Non-Goals`, `Design`, `Decision Log`, `Acceptance Criteria`, and `Existing Codebase Constraints` (when present) from the full design input set (root + sub docs when `root-sub`).
4. Read only ADRs linked from the design input set Decision Logs and linked `TEMPxx` lifecycle records (root + sub docs when `root-sub`).
5. Build a **Design Atom Index** with stable IDs:
   - `GOALxx`: in-scope outcomes
   - `NONGOALxx`: explicit exclusions
   - `REQxx`: implementable requirements
   - `DECxx`: key design decisions; each must map to exactly one `ADR-xxxx` from Decision Log
   - `ACxx`: acceptance criteria
   - `TEMPxx`: temporary mechanisms from `Compatibility & Sunset` (required for breaking-change designs)
   - For each `TEMPxx`, capture lifecycle tuple:
     - `retirement_trigger`
     - `retirement_verification`
     - `removal_scope`
     - `closure_source` (`checklist` or `ledger`)
     - `record_source` (`adr` or `ledger`)
   - When `root-sub`, verify design-atom IDs are globally unique across root and all sub docs; if duplicate IDs exist, stop as `BLOCKED`.
6. Create a **Decision Trace** table: `DECxx -> ADR-xxxx`.
7. Identify test frameworks, canonical verification commands, and project-wide Quality Gates.
   - Detection source priority: `AGENTS.md` > `CLAUDE.md` > project config files (`package.json`, `Makefile`/`Taskfile.yml`, `pyproject.toml`, `.pre-commit-config.yaml`, CI config).
   - Classify each gate by category: `test`, `lint`, `format`, `typecheck`, `other`.
   - Record the exact executable command for each gate.
   - If no quality gates are found from any source, stop as `BLOCKED` and request the user to define quality gates (in `AGENTS.md`, `CLAUDE.md`, or a project config file) before proceeding.
   - For each gate command, verify the first token (space-delimited) is resolvable via `command -v`. If any command is not found, stop as `BLOCKED` and report the missing command(s).
8. Read `## Risk Classification` from the design doc:
   - For each task's change targets, inherit the highest risk tier from matching areas in the classification table.
   - If no `## Risk Classification` section exists:
     - If the design touches Critical domains (auth, billing, access control, encryption, PII), stop as `BLOCKED` and request a risk-classified design doc.
     - Otherwise (greenfield with no Critical-domain changes), treat all areas as Standard.
9. Run the design sufficiency gate:
   - If migration/breaking-change intent exists but `TEMPxx` lifecycle evidence is missing/incomplete, stop as `BLOCKED`.

### Step 2: Analyze and Decompose

1. Build a design-atom-to-component map from the design.
2. Build task dependencies (foundation before integration).
3. Create tasks that each deliver one verifiable increment.
4. For each `TEMPxx`, map lifecycle coverage in `Temporary Mechanism Trace` using existing implementation tasks:
   - Identify introducing, migrate/cutover, and retiring task IDs where applicable.
   - Do not create `TEMPxx`-only tasks or add `TEMPxx` fields to `plan.md` task blocks.
   - If retirement is intentionally deferred, record waiver metadata in the trace (`reason`, `deadline`, `owner` optional for solo operation).
   - When a retiring task is identified, ensure its DoD in `plan.md` includes negative verification that the `TEMPxx` removal is complete (fallback/temporary path must fail or be absent).
5. For each task, define `Allowed Files` as a list of glob patterns covering all files the task may Create or Modify. Patterns should be precise enough to detect unintended scope creep but broad enough to avoid false positives for expected paths.
5.1. For each task, optionally define `Exception Files` when the task legitimately needs to modify files outside `Allowed Files` (e.g., shared configuration, generated files). Each exception must include a rationale. Exception Files exempt the file from `SCOPE_DEVIATION` in dod-recheck but do not add it to `Allowed Files`.
5.5. For each AC with `Verification Command: TBD-at-plan` in the design doc, resolve the concrete command based on task context (test framework, verification approach). Record the resolved command in the task's RED or DoD. If a concrete command cannot be determined, stop as `BLOCKED`.
6. For each task, define `RED`, `GREEN`, `REFACTOR`, and `DoD` without implementation snippets.
   - Define RED as an executed test failure (assertion/runtime), not a compilation/import/module error.
   - If missing symbols/files would prevent compilation, require minimal scaffolding in the task so RED can be evaluated by executed tests.
   - If direct unit-level RED is technically difficult, require the nearest executable boundary test (integration/contract/e2e) while keeping fail-first.
   - Do not abandon TDD due to testability difficulty; add testability-enabling work and continue the RED loop.
   - Define DoD as strict AND semantics: all DoD items are mandatory, and none are optional alternatives.
   - If Quality Gates were detected in Step 1.7, append a quality gate reference line to every task DoD: `Run: all commands in \`## Quality Gates\`` / `Expected: all PASS`.
   - If the task's inherited risk tier is Critical, append to DoD: `Adversarial verification required (minimum 3 probes).`
   - If the task's inherited risk tier is Sensitive, append to DoD: `Heightened dod-recheck scrutiny applies`.
   - If the task's inherited risk tier is Sensitive, append to DoD: `Adversarial verification required (minimum 2 probes: Category 1 + most relevant 1 category).`
   - If the task's inherited risk tier is Standard and its Files contain implementation files (paths not matching `*test*`, `*spec*`, `*.md`, `docs/*`, `*.txt`), append to DoD: `Adversarial verification required (1 probe: most relevant category).`
7. Build a **Behavioral Lock Map** from design atoms:
   - Extract lock atoms: design wording, acceptance criteria, or constraint entries that express exclusivity, removal, replacement, or mandatory failure on a former path. Common keyword examples (not exhaustive): `only`, `remove`, `no fallback`, `fail-closed`, `唯一`, `廃止`, `禁止`.
   - Map each lock atom to one or more task-level negative checks and one positive boundary check.
   - If a lock atom cannot be mapped to executable checks, stop as `BLOCKED`.
8. Assign `Design Anchors` for each task:
   - Each task must map to at least one `REQxx` or `ACxx`.
   - If a task enforces a design decision, include `DECxx` in anchors.
   - `TEMPxx` IDs are not valid `Design Anchors` for `plan.md`; keep TEMP mapping in `plan.trace.md`.
   - Raw ADR IDs are not valid task anchors; always anchor via `DECxx`.
   - No task may exist without traceable design anchors.
9. **AC Ownership Assignment**:
   - For each `ACxx`, assign exactly one Owner Task (the task whose RED validates this AC) and zero or more Contributor Tasks.
   - The Owner Task must include RED for the AC.
   - Record in the `AC Ownership Map` (see Trace Pack required sections).
10. **Negative Path Coverage**:
   - For ACs with EARS Type=Unwanted or lock requirements (expressing exclusivity, removal, replacement, or mandatory failure on a former path), require at least one negative test in the Owner Task's RED or DoD.
11. **High-Risk Auto-Detection**:
    - ACs with EARS Type=Unwanted or lock requirements are automatically classified as high-risk.
    - Manual override of high-risk classification requires documented reason in the task.
12. Prepare task structure for granularity review:
   - Require every task to present a single stated objective, one main verification flow, and an explicit rollback boundary.
   - Apply the create-mode `Objective` / `Surface` / `Verification` / `Rollback` self-check to re-slice overloaded tasks before presentation.
   - If task structure is ambiguous enough that review mode would need extra inference, rewrite the task before presenting the plan.
   - Do not assign granularity scores, totals, or PASS/FAIL in create mode; review mode is the authoritative granularity gate.

### Step 3: Write Plan Bundle

1. Create output files:
   - `docs/plans/<topic>/plan.md`
   - `docs/plans/<topic>/plan.trace.md`
   - `docs/plans/<topic>/plan.compose.md`
2. Write `plan.md` as compact execution instructions.
3. Write `plan.trace.md` with Design Atom Index, Decision Trace, both matrices, Behavioral Lock Map, and full check details.
4. Write `plan.compose.md` with reconstruction summary and scope diff.
5. Ensure `plan.md` links to both sidecars in its header.
6. Ensure each task in `plan.md` references `REQxx/ACxx` in `Satisfied Requirements` and has complete `Design Anchors`.
7. Ensure each `TEMPxx` has introducing/retiring task mappings (or explicit waiver metadata) in `plan.trace.md`.
8. Write `Checkpoint Summary` in `plan.md` using the required fixed format.

### Step 4: Structural Self-Check (Required)

Perform structural checks before presenting the plan. Semantic verification is delegated to review mode.

1. Run `<skill-root>/scripts/structural-check.sh <design-file> <plan-file>`.
2. If any check reports FAIL, fix the affected tasks and re-run until all PASS.
3. Do NOT present the plan to the user if structural checks are failing.
4. Record structural check results in `plan.trace.md`.
5. When writing commands or file paths into `plan.trace.md`, use repository-relative project paths and `scripts/<name>.sh` helper names, never absolute filesystem paths.
6. Update `Checkpoint Summary` in `plan.md`.

**Note**: The deep semantic checks (forward/reverse fidelity, behavioral lock guard, granularity scoring, temporal completeness, etc.) are now performed by `decompose-plan review` mode, which runs as an independent sub-agent.
The review agent writes `plan.review.draft.md`, and a finalizer script produces the gate artifact `plan.review.md`.

### Step 5: Review with User

1. Present the compact `plan.md` first.
2. Mention that detailed traceability is in `plan.trace.md` and reconstruction evidence is in `plan.compose.md`.
3. Apply feedback and update all impacted files.
4. If feedback splits, merges, reorders, removes, renames, or adds tasks, treat dependency updates as whole-plan impact analysis: update the Task Dependency Graph, the changed tasks, and every other task whose `Dependencies`, ordering, or prerequisite assumptions reference the changed task IDs or boundaries (for example, if `T3` is split, also update each downstream `T<N>` that depended on `T3`). Do not limit the fix to the changed task itself.
5. Re-run Structural Self-Check after each meaningful change.
6. Repeat until the user explicitly approves.
7. After approval, suggest running `decompose-plan review` (independent sub-agent verification) before `execute-plan`.

## Key Principles

- **Design Fidelity (YAGNI)**: Plan only what design atoms require. Do not add behavior outside approved design scope.
- **Requirement Traceability (Exact over vague)**: Every task and DoD must map to explicit design IDs and concrete verification commands.
- **TDD Discipline**: Every task includes `RED -> GREEN -> REFACTOR`.
- **RED Validity**: RED means test execution fails for expected behavior reasons; compilation errors indicate incomplete scaffolding, not valid RED.
- **No TDD Abandonment**: Testability difficulty is resolved by scaffolding or boundary-level tests, not by skipping RED.
- **DoD Conjunction**: DoD is always AND semantics; all DoD items must be satisfied.
- **Maintainability (DRY)**: Avoid duplicated task intent; express shared logic once via trace matrices and dependency graph.
- **Execution Rhythm (Frequent Commits Principle)**: Keep task boundaries reviewable by exposing clear task structure in create mode and delegating granularity scoring to the independent review flow.
- **Instruction over Implementation**: Describe intent and verification, not code.
- **No Micromanagement**: Avoid over-splitting and line-by-line directives.
- **Context Efficiency**: Keep frequently-read artifacts compact; move heavy evidence to on-demand sidecars.
- **Round-Trip Integrity**: The composed tasks must reconstruct the design doc scope without loss or scope creep.
- **Lifecycle Closure by Construction**: Temporary mechanisms must have explicit create/migrate/retire paths in plan artifacts.
- **Fail-Closed Decomposition**: If lifecycle data is missing in design, stop as `BLOCKED` instead of inferring.
- **Behavioral Lock Integrity**: Replacement/removal/fail-closed intent must be encoded as executable negative checks, not prose-only promises.
