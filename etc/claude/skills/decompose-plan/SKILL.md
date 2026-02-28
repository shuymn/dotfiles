---
name: decompose-plan
description: Decomposes an approved design document into a TDD-based implementation plan with task breakdown and traceability. Use after design-doc approval when the user needs to break down a design into executable tasks, create an implementation plan, or generate a task list from a design.
allowed-tools: [Read, Write, Edit, Grep, Glob, TodoWrite, Bash]
---

# Task Decomposition from Design Doc

Convert an approved design doc into a concise, execution-ready plan bundle.
Output instruction-level guidance only. Do not output implementation code snippets.

## Input / Output

- Input: a design doc in `docs/plans/` (typically created by the `design-doc` skill).
  - If the design doc declares `Split Decision: root-sub`, treat the root doc plus all sub docs listed in its `Sub-Doc Index` as the design input set.
- Output is a 3-file bundle:
  - `docs/plans/YYYY-MM-DD-<topic>-plan.md` (core, frequently read)
  - `docs/plans/YYYY-MM-DD-<topic>-plan.trace.md` (traceability evidence, on-demand)
  - `docs/plans/YYYY-MM-DD-<topic>-plan.compose.md` (reconstruction check, on-demand)

## <HARD-GATE>

Do NOT begin any implementation until the plan is explicitly approved by the user.
Reason: implementing against an unapproved plan locks in scope decisions the user hasn't seen yet; adjusting the plan before code is written is far cheaper than reverting code afterward.

No exceptions. Not even "just to test one thing" or "the first task is trivial."

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

### Core Plan (`...-plan.md`) Required Sections

1. Header
2. Task Dependency Graph (compact form)
3. Task list (`Goal`, `RED`, `GREEN`, `REFACTOR`, `DoD`, lifecycle metadata when `TEMPxx` exists)
4. Checkpoint Summary

### Trace Pack (`...-plan.trace.md`) Required Sections

1. Design Atom Index
2. Decision Trace (`DECxx -> ADR-xxxx`)
3. Design -> Task Trace Matrix
4. Task -> Design Compose Matrix
5. Temporary Mechanism Trace (`TEMPxx` lifecycle and closure status)
6. Full Cross Self-Check evidence

### Compose Pack (`...-plan.compose.md`) Required Sections

1. Reconstructed design summary from tasks
2. Scope diff (`missing`, `extra`, `ambiguous`)
3. Alignment verdict and required fixes

### Link Contract (Required)

`plan.md` header must include:

- `**Trace Pack**: docs/plans/YYYY-MM-DD-<topic>-plan.trace.md`
- `**Compose Pack**: docs/plans/YYYY-MM-DD-<topic>-plan.compose.md`

### Templates

- **Plan templates** (header, checkpoint summary, task structure): See [plan-templates.md](references/plan-templates.md)
- **Trace templates** (trace matrices, cross self-check, compose reconstruction): See [trace-templates.md](references/trace-templates.md)

### Compression Rules

- Keep `plan.md` concise: no duplicated requirement prose, no full trace matrices, no long rationale blocks.
- Prefer stable IDs (`REQxx`, `ACxx`, `DECxx`) over repeated natural-language restatement.
- Put exhaustive mapping and diagnostics into sidecars.
- Keep each task minimal but executable; avoid narrative that does not change implementation behavior.

### Strict Scope Rules

- Do not include code blocks for test or implementation in the plan bundle.
- Do not prescribe line-by-line implementation details.
- Do not add features outside the design doc.
- Keep each task outcome independently testable.
- Keep task granularity at one coherent, reviewable change unit; do not include commit commands or require commit execution.
- Do not use fixed file-count or LOC thresholds as hard rules.
- Apply granularity triage:
  - Hard gate (must pass): one primary objective, one main verification flow, and a clear rollback boundary.
  - Split signals (if 2+ signals, split by default): unrelated components/domains, unrelated `REQxx/ACxx` targets, multiple independent verification environments/commands, or inability to rollback part of the task safely.
  - Waiver rule: if you keep a task unsplit despite split signals, add explicit waiver metadata in the task (`reason`, `added risk`, `rollback plan`).

## Process

### Step 1: Load Design Doc

1. Read the design doc specified by the user.
2. Detect decomposition strategy from `## Decomposition Strategy`:
   - If `Split Decision: single`, continue with the single design doc.
   - If `Split Decision: root-sub`, read all sub docs listed in `Sub-Doc Index`.
   - If `root-sub` is declared but `Sub-Doc Index` is missing or any listed sub doc is unreadable, stop as `BLOCKED`.
3. Read `Goals`, `Non-Goals`, `Design`, `Decision Log`, and `Acceptance Criteria` from the full design input set (root + sub docs when `root-sub`).
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
7. Identify test frameworks and canonical verification commands.
8. Run the design sufficiency gate:
   - If migration/breaking-change intent exists but `TEMPxx` lifecycle evidence is missing/incomplete, stop as `BLOCKED`.

### Step 2: Analyze and Decompose

1. Build a design-atom-to-component map from the design.
2. Build task dependencies (foundation before integration).
3. Create tasks that each deliver one verifiable increment.
4. For each `TEMPxx`, enforce lifecycle slicing by construction:
   - `Introduce` task (creates temporary mechanism)
   - `Migrate/Cutover` task(s) (moves consumers/data/paths)
   - `Retire` task (removes temporary mechanism and fallback paths)
   - If retirement is intentionally deferred, create explicit waiver metadata (reason, deadline, owner optional for solo operation).
5. For each task, define `RED`, `GREEN`, `REFACTOR`, and `DoD` without implementation snippets.
   - Define RED as an executed test failure (assertion/runtime), not a compilation/import/module error.
   - If missing symbols/files would prevent compilation, require minimal scaffolding in the task so RED can be evaluated by executed tests.
   - If direct unit-level RED is technically difficult, require the nearest executable boundary test (integration/contract/e2e) while keeping fail-first.
   - Do not abandon TDD due to testability difficulty; add testability-enabling work and continue the RED loop.
   - Define DoD as strict AND semantics: all DoD items are mandatory, and none are optional alternatives.
6. Assign `Design Anchors` for each task:
   - Each task must map to at least one `REQxx` or `ACxx`.
   - If a task enforces a design decision, include `DECxx` in anchors.
   - Tasks that create/retire temporary mechanisms must include `TEMPxx`.
   - Raw ADR IDs are not valid task anchors; always anchor via `DECxx`.
   - No task may exist without traceable design anchors.
7. Validate granularity quality:
   - Require all hard-gate properties to pass (single objective, single verification flow, clear rollback boundary).
   - Count split signals; if 2 or more, split by default.
   - If not splitting despite 2+ signals, record waiver metadata (`reason`, `added risk`, `rollback plan`).
   - If multiple tasks collapse into one indistinguishable change unit, merge or re-slice.

### Step 3: Write Plan Bundle

1. Create output files:
   - `docs/plans/YYYY-MM-DD-<topic>-plan.md`
   - `docs/plans/YYYY-MM-DD-<topic>-plan.trace.md`
   - `docs/plans/YYYY-MM-DD-<topic>-plan.compose.md`
2. Write `plan.md` as compact execution instructions.
3. Write `plan.trace.md` with Design Atom Index, Decision Trace, both matrices, and full check details.
4. Write `plan.compose.md` with reconstruction summary and scope diff.
5. Ensure `plan.md` links to both sidecars in its header.
6. Ensure each task in `plan.md` references `REQxx/ACxx` in `Satisfied Requirements` and has complete `Design Anchors`.
7. Ensure each `TEMPxx` has `Creates` and `Retires` coverage (or explicit waiver metadata) in tasks.
8. Write `Checkpoint Summary` in `plan.md` using the required fixed format.

### Step 4: Cross Self-Check (Required)

Perform all checks before presenting the plan. Use templates from [trace-templates.md](references/trace-templates.md).

1. Forward fidelity (`design -> tasks`)
   - Every `REQxx` and `ACxx` must appear in at least one task `Satisfied Requirements`.
   - Every `REQxx` and `ACxx` must appear in at least one task `DoD`.
   - `GOALxx` must be covered by one or more tasks.
   - Every `DECxx` must appear in at least one task `Design Anchors`.
   - Every `DECxx` must have exactly one `ADR-xxxx` mapping in Decision Trace.
2. Reverse fidelity (`tasks -> design`)
   - Reconstruct design intent using only task `Design Anchors`, `Goal`, `GREEN`, and `DoD`.
   - Verify the reconstructed result preserves source design scope, key decisions, and acceptance intent.
   - Verify every task anchor points to an existing design atom.
   - Verify every task has at least one `REQxx` or `ACxx` in `Satisfied Requirements`.
3. Non-goal guard
   - Verify no task maps to `NONGOALxx`.
   - Verify no task introduces behavior outside mapped design atoms.
4. DoD semantics guard
   - Verify each task treats DoD as AND (all items mandatory, no OR wording).
   - Verify each DoD item is independently verifiable.
5. Granularity guard
   - Verify each task passes hard-gate properties (single objective, single verification flow, clear rollback boundary).
   - Count split signals per task; when 2+ signals exist, verify task is split or has waiver metadata.
   - Flag overly broad, fragmented, or unjustified waived tasks.
6. Temporal completeness guard
   - Every `TEMPxx` must map to at least one introducing task and one retiring task.
   - Every retiring task DoD must include negative verification of fallback/temporary-path removal.
   - `Open TEMPxx` entries are allowed only with explicit waiver metadata (reason, deadline, owner optional for solo operation).
7. Round-trip gate
   - Mark `Alignment verdict: PASS` only when forward fidelity, reverse fidelity, non-goal guard, DoD semantics guard, granularity guard, and temporal completeness guard all pass.
   - If any check fails: identify failing items → revise affected tasks → re-run all checks from step 1.
   - Repeat until all checks pass.
8. Record results:
   - Full evidence in `plan.trace.md`
   - Reconstructed summary and scope diff in `plan.compose.md`
   - `TEMPxx introduced/retired/open/waived` counts in `Checkpoint Summary`
   - Update `Checkpoint Summary` in `plan.md`

### Step 5: Review with User

1. Present the compact `plan.md` first.
2. Mention that detailed traceability is in `plan.trace.md` and reconstruction evidence is in `plan.compose.md`.
3. Apply feedback and update all impacted files.
4. Re-run Cross Self-Check after each meaningful change.
5. Repeat until the user explicitly approves.
6. After approval, suggest running `analyze-plan` before `setup-ralph` or `execute-plan`.

## Key Principles

- **Design Fidelity (YAGNI)**: Plan only what design atoms require. Do not add behavior outside approved design scope.
- **Requirement Traceability (Exact over vague)**: Every task and DoD must map to explicit design IDs and concrete verification commands.
- **TDD Discipline**: Every task includes `RED -> GREEN -> REFACTOR`.
- **RED Validity**: RED means test execution fails for expected behavior reasons; compilation errors indicate incomplete scaffolding, not valid RED.
- **No TDD Abandonment**: Testability difficulty is resolved by scaffolding or boundary-level tests, not by skipping RED.
- **DoD Conjunction**: DoD is always AND semantics; all DoD items must be satisfied.
- **Maintainability (DRY)**: Avoid duplicated task intent; express shared logic once via trace matrices and dependency graph.
- **Execution Rhythm (Frequent Commits Principle)**: Keep task boundaries at one coherent change unit using hard-gate/split-signal triage rather than fixed size thresholds.
- **Instruction over Implementation**: Describe intent and verification, not code.
- **No Micromanagement**: Avoid over-splitting and line-by-line directives.
- **Context Efficiency**: Keep frequently-read artifacts compact; move heavy evidence to on-demand sidecars.
- **Round-Trip Integrity**: The composed tasks must reconstruct the design doc scope without loss or scope creep.
- **Lifecycle Closure by Construction**: Temporary mechanisms must have explicit create/migrate/retire paths in plan artifacts.
- **Fail-Closed Decomposition**: If lifecycle data is missing in design, stop as `BLOCKED` instead of inferring.
