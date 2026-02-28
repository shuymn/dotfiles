---
name: analyze-plan
description: Audits an approved plan bundle for execution readiness before implementation begins. Trigger after plan approval and before setup-ralph or execute-plan. Produces a PASS/FAIL analysis report verifying bundle integrity, traceability, scope, and testability.
allowed-tools: [Read, Write, Edit, Grep, Glob, TodoWrite, Bash]
---

# Plan Analysis Gate

Run an independent quality gate on an approved plan bundle before execution.
Write one analysis artifact and block downstream execution when critical issues exist.

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
   - `Granularity Guard`
   - `Temporal Completeness Guard`
   - `Trace Pack`
   - `Compose Pack`
   - `Updated At`
5. Resolve `Source` design doc path from the plan header when present.
6. If `Source` exists, read it and detect whether it declares `Split Decision: root-sub` under `## Decomposition Strategy`.

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
   - Verify each `TEMPxx` has both create-side and retire-side task coverage, or explicit waiver metadata.
   - Verify retire task DoD includes negative verification for temporary-path/fallback removal.
7. **Ambiguity and Risk**
   - Identify vague directives that can cause divergent implementations.
   - Identify oversized or fragmented task boundaries.
8. **Design Partition Integrity** (only when source design uses `Split Decision: root-sub`)
   - Verify source design contains `## Decomposition Strategy`.
   - Verify source design includes explicit boundary ownership and a sub-doc index.
   - Verify source design includes a root coverage table mapping root requirements/acceptance criteria to sub-doc owners or integration work.
   - If any of the above are missing, mark blocker (decomposition basis is under-specified).

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
- Design Partition Integrity: PASS | FAIL | N/A (single-doc design)
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
- Missing `TEMPxx` retirement coverage in a breaking-change plan is a blocker.
- Missing root/sub decomposition evidence in source design (when `Split Decision: root-sub`) is a blocker.
- `Design Partition Integrity` may be `N/A` only when source design does not declare `Split Decision: root-sub`.

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
- Breaking-change intent exists but temporal/lifecycle evidence (`TEMPxx` trace) is missing.
- The user asks to modify plan content during this analysis flow.
- The user asks to implement tasks during this analysis flow.

## Key Principles

- **Independent Verification**: Re-check critical properties even if prior checkpoints reported PASS.
- **Fail-Closed Readiness**: Default to FAIL when readiness evidence is missing.
- **Actionable Findings**: Every blocker must include a concrete correction path.
- **Execution Safety**: Do not allow downstream execution on ambiguous or unverified plan state.
- **Temporal Closure Safety**: Do not pass plans that introduce temporary mechanisms without validated retirement paths.
