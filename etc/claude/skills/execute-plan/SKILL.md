---
name: execute-plan
description: Executes exactly one explicitly user-selected task from an approved and analyzed decompose-tasks plan bundle. Use when the user specifies a concrete task ID from docs/plans/YYYY-MM-DD-{topic}-plan.md after analyze-plan PASS, with on-demand reads of plan.trace.md and plan.compose.md.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, TodoWrite, Task]
---

# Plan Execution

Execute one selected task from an approved plan bundle.
Do not continue to other tasks unless the user explicitly asks in a new instruction.

## When to Use

- You have an approved plan bundle from `decompose-tasks`.
- `analyze-plan` has produced `...-plan.analysis.md` with PASS verdict.
- The user explicitly asks to execute a specific task (for example, `Task 7`).
- Input includes:
  - `docs/plans/YYYY-MM-DD-<topic>-plan.md` (primary)
  - `docs/plans/YYYY-MM-DD-<topic>-plan.trace.md` (on-demand traceability evidence)
  - `docs/plans/YYYY-MM-DD-<topic>-plan.compose.md` (on-demand reconstruction evidence)
  - `docs/plans/YYYY-MM-DD-<topic>-plan.analysis.md` (required readiness gate)

## <HARD-GATE: TASK SELECTION>

Never choose a task implicitly.

- Require an explicit task ID before any implementation step.
- The task ID may be specified by the user directly, or by a calling agent (e.g., ralph runtime's Task Selection Algorithm).
- If task ID is missing, ask for it and stop.
- Do not infer from dependency order, priority, first pending task, or any heuristic on your own.

## Process

### Step 1: Load Bundle and Select One Task

1. Read `plan.md`.
2. Resolve `Trace Pack` and `Compose Pack` paths from the plan header.
3. Confirm the target task ID:
   - Use only the task ID explicitly specified by the user.
   - If not explicitly specified, ask which task ID to execute and stop.
   - Never auto-select a task.
4. Validate bundle consistency:
   - `plan.md` exists and includes the selected task ID.
   - Referenced sidecars exist.
   - `Checkpoint Summary` exists and uses required keys:
     - `Alignment Verdict`
     - `Forward Fidelity`
     - `Reverse Fidelity`
     - `Non-Goal Guard`
     - `Granularity Guard`
     - `Trace Pack`
     - `Compose Pack`
     - `Updated At`
   - `Checkpoint Summary` has `Alignment Verdict: PASS`.
   - `Checkpoint Summary` `Trace Pack` and `Compose Pack` values match header links.
   - Analysis report exists at `...-plan.analysis.md` (replace `-plan.md` with `-plan.analysis.md`) and has:
     - `Overall Verdict: PASS`
     - `Bundle Integrity: PASS`
     - `Traceability Integrity: PASS`
     - `Scope Integrity: PASS`
     - `Testability Integrity: PASS`
     - `Execution Readiness: PASS`
5. Check task dependencies:
   - Treat dependency status as satisfied only when the user explicitly confirms prerequisites are already satisfied.
   - If explicit user confirmation is missing, stop and ask for confirmation.
6. Read source design doc linked in header for acceptance context.
7. Read sidecars only when needed:
   - `plan.trace.md` for requirement/anchor ambiguity.
   - `plan.compose.md` for scope ambiguity.
8. Register only the selected task in TodoWrite (`pending` -> `in_progress` -> `completed`).

If validation fails, stop and ask for plan correction before implementation.

### Step 2: Execute Selected Task

1. Execute the selected task exactly per task contract:
   - `RED`: create failing test. If referenced implementation symbols/files do not exist, add minimal scaffolding first so the test compiles and runs. RED is valid only when the test runner executes the test and fails (assertion/runtime); compilation/import/module errors are not valid RED.
   - If direct unit-level RED is technically difficult, apply this recovery loop in order: (1) add minimal seams/scaffolding, (2) retry unit-level RED, (3) move to nearest executable boundary test (integration/contract/e2e) while preserving fail-first.
   - Do not abandon implementation solely because testing is difficult. Continue until executable RED is established or a true blocker is reached.
   - `GREEN`: implement minimal code to pass RED.
   - `REFACTOR`: perform safe cleanup while keeping tests green.
   - `DoD`: treat all DoD items as AND conditions. Task completion requires every DoD item to pass.
2. Verify expected outputs after each step before proceeding.
3. Mark the task as `completed` in TodoWrite.

If expected results are not met, stop and follow Stop Conditions.

### Step 3: Report and Stop

1. Summarize what was implemented for this single task.
2. Provide verification evidence (commands, key outputs, exit codes).
3. Explicitly stop after this task.
4. If the user wants another task, ask them to specify the next task ID.

## Stop Conditions

Stop immediately and ask user guidance when:

- Plan bundle validation fails (missing sidecar, invalid summary, broken links).
- Analysis report is missing, malformed, or has any verdict that is not PASS.
- Target task ID is missing, ambiguous, or not explicitly provided by the user.
- Dependency satisfaction was not explicitly confirmed by the user.
- RED cannot reach executable failing state after applying the RED recovery loop.
- GREEN cannot reach pass state.
- Any DoD item fails verification (DoD is AND, not OR).
- A task anchor/requirement mapping is unclear and cannot be resolved from `plan.md`.
- Sidecar evidence contradicts `plan.md`.
- Verification fails **3 or more times** for the same step.

When stopped:

- Report command, output, expected vs actual.
- Do not guess a fix.
- Do not modify the plan bundle without user approval.
- Wait for user decision.

## On-Demand Read Policy

- Default to `plan.md` during execution.
- Read `plan.trace.md` only to resolve mapping/coverage ambiguity.
- Read `plan.compose.md` only to resolve scope ambiguity.
- After resolving, return to `plan.md`.
- Do not repeatedly re-read full sidecars unless a new ambiguity appears.

## Verification Principle

Before claiming task completion:

1. Identify the exact verification command.
2. Run it fresh.
3. Read full output and exit code.
4. Confirm evidence matches the claim.
5. State claim with evidence.

Avoid unevidenced completion claims.

## Adapting to Plan Deviations

| Situation | Action |
|-----------|--------|
| Test command in task is invalid | Apply minimal command correction, record deviation |
| Minor implementation adjustment needed | Make minimal adjustment, record deviation |
| Task is materially larger than planned scope | STOP; request plan reslicing |
| Missing prerequisite not captured by task | STOP; report dependency gap |
| Dependency completion is uncertain | Ask user for explicit confirmation and STOP |
| Test passes before intended change | STOP; plan may be stale |
| Sidecar and `plan.md` conflict | STOP; request plan bundle correction |
| User asks to continue immediately to another task | STOP current turn and request explicit next task ID |
| User asks to run execute-plan without task ID | Ask for explicit task ID and STOP |
