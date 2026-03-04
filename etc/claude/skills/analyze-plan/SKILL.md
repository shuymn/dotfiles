---
name: analyze-plan
description: Audits an approved plan bundle for execution readiness before implementation begins. Trigger after plan approval and before setup-ralph or execute-plan. Produces a PASS/FAIL analysis report verifying bundle integrity, traceability, scope, and testability.
allowed-tools: [Read, Write, Edit, Grep, Glob, TodoWrite, Bash]
---

# Plan Analysis Gate

Run an independent quality gate on an approved plan bundle before execution.
Write one analysis artifact and block downstream execution when critical issues exist.

## Markdown Formatting Contract

- Never rely on soft line breaks for visible separation in rendered markdown.
- For key-value metadata, always use list or table syntax (preferred: `- **Key**: value`).

## When to Use

- A plan bundle has been created by `decompose-plan` and explicitly approved by the user.
- You are preparing to run `setup-ralph` or `execute-plan`.
- Input: an approved `docs/plans/YYYY-MM-DD-<topic>-plan.md` and its sidecars.
- Output: `docs/plans/YYYY-MM-DD-<topic>-plan.analysis.md`.

## Not in Scope

- Modifying plan.md, design docs, or any source code.
- Suggesting architectural improvements or alternative designs.
- Running `setup-ralph` or `execute-plan` — this skill only produces the analysis report.

## <HARD-GATE>

Do NOT implement any task while running this skill.
Reason: implementation during analysis contaminates the independence of the quality gate — the same agent both writing and auditing cannot reliably catch its own blind spots.

- Do not edit source code or plan/design artifacts while analyzing.
- Write only the analysis report.

## Output

Write:

- `docs/plans/YYYY-MM-DD-<topic>-plan.analysis.md`

Path rule:

- Derive from plan path by replacing `-plan.md` with `-plan.analysis.md`.

## Process

### Step 1: Load Bundle and Validate Inputs

1. Read `plan.md`.
2. Resolve `Trace Pack` and `Compose Pack` from the plan header.
3. Validate files exist and header links match actual paths.
4. Validate `Checkpoint Summary` keys exist:
   - `Alignment Verdict`
   - `Forward Fidelity`
   - `Reverse Fidelity`
   - `Non-Goal Guard`
   - `Behavioral Lock Guard`
   - `Granularity Guard`
   - `Temporal Completeness Guard`
   - `Quality Gate Guard`
   - `Integration Coverage Guard`
   - `Trace Pack`
   - `Compose Pack`
   - `Updated At`
5. Resolve `Source` design doc path from the plan header when present.
6. If `Source` exists, read it and detect whether it declares `Split Decision: root-sub` under `## Decomposition Strategy`.
7. If the plan/trace includes `TEMPxx` work and `Source` is missing or unreadable, stop as `BLOCKED` (cannot validate in-doc closure evidence).
8. Build a lock-atom candidate list from source design and plan terms (`only`, `must not`, `remove`, `retire`, `no fallback`, `fail-closed`, `唯一`, `廃止`, `禁止`).

### Step 2: Independent Analysis (Do Not Trust Prior Verdict Blindly)

Evaluate each area independently and record PASS/FAIL with evidence.

1. **Bundle Integrity**
   - Required files exist and links are not broken.
   - Header link values and summary values are consistent.
2. **Traceability Integrity**
   - Every task has `Design Anchors`.
   - Every task has `Satisfied Requirements` referencing stable IDs (`REQxx`/`ACxx`).
   - Validate all task anchors and requirement references against design atoms (no sampling).
3. **Scope Integrity**
   - No task appears to implement explicit non-goals.
   - Check compose sidecar for unresolved `missing`, `extra`, or `ambiguous` scope items.
4. **Testability Integrity**
   - Every task defines `RED`, `GREEN`, `REFACTOR`, and `DoD`.
   - RED statements describe executable failing tests (not compile/import failure states).
   - DoD items are verifiable and written as AND semantics.
5. **Execution Readiness**
   - Verification commands are concrete and runnable in principle.
   - Flag missing/unclear commands, unknown tools, or environment assumptions that are not documented.
6. **Temporal Integrity**
   - Validate `TEMPxx` lifecycle trace exists when plan includes staged migration/breaking-change work.
   - Verify each `TEMPxx` has in-doc closure summary evidence in the source design doc (`## Compatibility & Sunset`: checklist/ledger row) with closure tuple fields (`retirement_trigger`, `retirement_verification`, `removal_scope`).
   - Verify each `TEMPxx` declares lifecycle record source (`adr` or `ledger`); when `adr`, verify linked ADR includes matching `Sunset Clause`.
   - Resolve `TEMPxx` lifecycle coverage exclusively from `Temporary Mechanism Trace` in `plan.trace.md`; task blocks in `plan.md` do not carry `Creates/Retires` fields.
   - Verify each `TEMPxx` has both create-side and retire-side task coverage (or explicit waiver metadata) in the trace.
   - For each `TEMPxx` with a retire task ID in the trace, verify that task's DoD in `plan.md` includes negative verification for temporary-path/fallback removal.
7. **Ambiguity and Risk**
   - Identify vague directives that can cause divergent implementations.
   - Identify oversized or fragmented task boundaries.
8. **Quality Gate Integrity**
   - Detect whether `## Quality Gates` section exists in `plan.md`.
   - If `## Quality Gates` is present: verify each listed command is concrete and runnable in principle.
   - If `## Quality Gates` is present: verify every task DoD contains `Run: all commands in \`## Quality Gates\``.
   - If `## Quality Gates` is absent: verify no task DoD contains the quality gate reference line (no phantom references).
   - Verify `Quality Gate Guard` in `Checkpoint Summary` is `PASS` or `N/A (no quality gates detected)`, not `FAIL`.
   - If `Quality Gate Guard` is `N/A` but `## Quality Gates` exists, or vice versa, flag as inconsistency blocker.
9. **Design Partition Integrity** (only when source design uses `Split Decision: root-sub`)
   - Verify source design contains `## Decomposition Strategy`.
   - Verify source design includes explicit boundary ownership and a sub-doc index.
   - Verify source design includes a root coverage table mapping root requirements/acceptance criteria to sub-doc owners or integration work.
   - If any of the above are missing, mark blocker (decomposition basis is under-specified).
10. **Behavioral Lock Integrity**
   - For each lock atom, verify plan tasks/DoD include at least one negative executable check proving forbidden paths fail.
   - Verify each lock atom has at least one positive boundary-level verification command (integration/contract/CLI smoke) when scope crosses runtime boundaries.
   - Mark blocker when lock atoms are represented only by prose and not by executable checks.
11. **Integration Coverage Integrity**
   - Identify cross-task boundaries: pairs (A, B) where task B's `**Dependencies**` field lists task A.
   - For each cross-task boundary, verify at least one of the spanning tasks has a boundary-level test command (integration/contract/e2e — not a package-local unit test against a mock substitute) in its RED or DoD.
   - Mark blocker when any cross-task boundary has no boundary-level test in any spanning task's RED or DoD.
   - Mark N/A when no task in the plan has a non-empty `**Dependencies**` field.

### Step 3: Write Analysis Report

Write `...-plan.analysis.md` with this structure:

```markdown
# <Topic> - Plan Analysis

## Summary

- Overall Verdict: PASS | FAIL
- Bundle Integrity: PASS | FAIL
- Traceability Integrity: PASS | FAIL
- Scope Integrity: PASS | FAIL
- Testability Integrity: PASS | FAIL
- Execution Readiness: PASS | FAIL
- Temporal Integrity: PASS | FAIL
- Quality Gate Integrity: PASS | FAIL | N/A (no quality gates detected)
- Design Partition Integrity: PASS | FAIL | N/A (single-doc design)
- Behavioral Lock Integrity: PASS | FAIL
- Integration Coverage Integrity: PASS | FAIL | N/A (no cross-task deps)
- Updated At: YYYY-MM-DD HH:MM TZ

## Findings

| ID | Severity | Area | File/Section | Issue | Action |
|----|----------|------|--------------|-------|--------|
| A1 | blocker/warn/info | Traceability | Task 3 | ... | ... |

## Blocking Issues

- [ ] [Issue that must be fixed before execution]

## Non-Blocking Improvements

- [Suggestion]

## Decision

- Proceed to `setup-ralph` / `execute-plan`: yes/no
- Reason:
```

Rules:

- `Overall Verdict: PASS` only when there are no blocking issues.
- If any blocker exists, set `Overall Verdict: FAIL`.
- Keep findings specific and actionable. Avoid generic wording.
- Missing `TEMPxx` checklist/ledger closure summary, closure tuple, or retirement coverage in a breaking-change plan is a blocker.
- `TEMPxx` work exists but source design doc is missing/unreadable is a blocker.
- Missing root/sub decomposition evidence in source design (when `Split Decision: root-sub`) is a blocker.
- `Quality Gate Integrity` may be `N/A` only when `## Quality Gates` is absent and no task DoD contains the reference line.
- Mismatch between `Quality Gate Guard: N/A` and presence of `## Quality Gates` (or reference lines) is a blocker.
- Missing executable negative checks for lock atoms (`only/remove/no-fallback/fail-closed`) is a blocker.
- Runtime-boundary replacement scope with no boundary-level verification command is a blocker.
- Any cross-task boundary with no boundary-level test (integration/contract/e2e) in any spanning task's RED or DoD is a blocker.
- `Design Partition Integrity` may be `N/A` only when source design does not declare `Split Decision: root-sub`.
- `Integration Coverage Integrity` may be `N/A` only when the plan has no cross-task dependency edges.

### Step 4: Review with User

1. Present only a concise summary of findings.
2. If verdict is FAIL, request plan corrections and re-run `analyze-plan` after fixes.
3. If verdict is PASS, suggest `setup-ralph` as next step.

## Stop Conditions

Stop and ask for user guidance when:

- Plan path is missing or invalid.
- `Trace Pack` or `Compose Pack` is missing.
- Plan format is malformed and cannot be analyzed reliably.
- Source design path is declared but unreadable.
- Plan/trace includes `TEMPxx` work but `Source` design doc path is missing.
- Breaking-change intent exists but temporal/lifecycle evidence (`TEMPxx` trace, checklist/ledger closure summary, or closure tuple fields) is missing.
- Lock-atom intent exists but executable negative verification is missing.
- The user asks to modify plan content during this analysis flow.
- The user asks to implement tasks during this analysis flow.

## Key Principles

- **Independent Verification**: Re-check critical properties even if prior checkpoints reported PASS.
- **Fail-Closed Readiness**: Default to FAIL when readiness evidence is missing.
- **Actionable Findings**: Every blocker must include a concrete correction path.
- **Execution Safety**: Do not allow downstream execution on ambiguous or unverified plan state.
- **Temporal Closure Safety**: Do not pass plans that introduce temporary mechanisms without validated retirement paths.
- **False-PASS Resistance**: Reject plans that can pass document checks while still allowing legacy/fallback behavior due to missing lock tests.
