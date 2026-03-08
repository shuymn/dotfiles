# DoD Recheck Mode

> `<skill-root>` means the directory containing the parent `SKILL.md`. Resolve `scripts/...` and `references/...` relative to `<skill-root>`, not to this file's location.

Independent verification of a completed task's DoD. This mode runs as a sub-agent (`fork_context=false`) in a separate session because the implementing agent cannot reliably catch its own blind spots.

## Constraints

- The rechecking agent must NOT have implemented the task being rechecked.
- Do NOT modify any code, plan, or design artifacts.
- Read-only + command execution only.

## Input

- Plan bundle path + task ID
- Recheck Input block (from implement mode's Step 3 output)

## Procedure

1. **Generate Header**: Run `skit digest-stamp dod-recheck <plan-file>` for the common source metadata, then append task-scoped metadata:
   - `Task ID`
   - `Task Contract Digest`
   - `Base Commit`
   - `Implementation Files`
   - `Boundary Changes`
2. **Re-execute DoD Commands**: Run each DoD command fresh and record command, exit code, expected outcome, actual outcome, and PASS/FAIL.
3. **Re-execute Quality Gate Commands**: If Quality Gates are listed in the Recheck Input, run each command fresh and record PASS/FAIL.
4. **Scope Contract Verification**:
   - Run: `git diff --name-only <base> | skit file-scope-check <plan-file> --task <N>`
   - The checker reads `Owned Paths`, `Shared Touchpoints`, and `Prohibited Paths` from the task's `Scope Contract`.
   - Record findings in `## File Scope Findings`:

     | # | File | Matched Pattern | Status |
     |---|------|----------------|--------|
     | 1 | [path] | [pattern or NONE] | OWNED_OK / SHARED_OK / CROSS_BOUNDARY / PROHIBITED |

   - Verdict policy:
     - `PROHIBITED`: FAIL
     - `CROSS_BOUNDARY`: completion revoked; plan re-slice required
     - `SHARED_OK`: PASS allowed, but record advisory context
     - `OWNED_OK`: normal PASS
5. **Inspection Surface**:
   - Sensitive/Critical: perform heightened scrutiny and re-run fresh `Boundary Verification` commands.
   - Standard tasks with implementation files: perform standard inspection using the implementation files recorded in the Recheck Input and metadata.
6. **Compute Overall Verdict**:
   - PASS only when all DoD commands and Quality Gate commands PASS, `File Scope Findings` contain no `CROSS_BOUNDARY` or `PROHIBITED`, and heightened scrutiny has no `critical`/`high` findings.
7. **Write Recheck Report**: Output to `...-task-<N>.dod-recheck.md`.

## Heightened Scrutiny (Sensitive/Critical)

Inspect implementation diffs and task boundary behavior for:

- Unvalidated inputs at trust boundaries
- Missing error handling on failure paths
- Hardcoded values
- Silent failures
- Unsafe type coercions or unchecked casts
- Boundary verification that still closes only on mocks or harness substitutes

Severity policy:

- `critical`: exploitable or access-control/security defect. Forces FAIL.
- `high`: strong outage/state corruption risk. Forces FAIL.
- `warning`: advisory only.

## Standard Inspection (Standard with Implementation Files)

When the Recheck Input includes implementation files for a Standard-tier task, inspect those files for:

- Hardcoded values
- Silent failures

All findings are advisory `warning` severity unless they escalate the task into Sensitive/Critical territory and require reslicing.

## Output Format

```markdown
# <Topic> - Task <N> DoD Recheck

## Recheck Metadata

<digest-stamp output>
- **Task ID**: Task N
- **Task Contract Digest**: [sha256]
- **Base Commit**: [git commit]
- **Implementation Files**:
  - [repo-relative path]
- **Boundary Changes**: owned | shared | cross-boundary
- **Overall Verdict**: PASS | FAIL

## DoD Verification

| # | Command | Exit Code | Expected | Actual | Verdict |
|---|---------|-----------|----------|--------|---------|
| 1 | [command] | [code] | [expected] | [actual] | PASS/FAIL |

## Quality Gate Verification

| # | Command | Exit Code | Verdict |
|---|---------|-----------|---------|
| 1 | [command] | [code] | PASS/FAIL |

## File Scope Findings

<!-- Always present when scope verification runs; if there are no findings, emit a single no-op row or a short "none" note. -->

| # | File | Matched Pattern | Status |
|---|------|----------------|--------|
| 1 | [path] | [pattern or NONE] | OWNED_OK / SHARED_OK / CROSS_BOUNDARY / PROHIBITED |

## Heightened Scrutiny Findings

<!-- Present when Risk Tier is Sensitive or Critical. -->

| # | File | Line(s) | Category | Finding | Severity |
|---|------|---------|----------|---------|----------|
| 1 | [path] | [lines] | [category] | [description] | critical/high/warning |

## Standard Inspection Findings

<!-- Present when Risk Tier is Standard and Implementation Files include implementation code. -->

| # | File | Line(s) | Category | Finding | Severity |
|---|------|---------|----------|---------|----------|
| 1 | [path] | [lines] | [category] | [description] | warning |

## Decision

- Task <N> completion: confirmed/revoked
- Reason: [rationale]
```

## Task Completion Definition

A task is complete only when both conditions hold:

1. Implement mode passes all RED/GREEN/REFACTOR/DoD steps.
2. DoD Recheck mode confirms the task on the current task contract.

If `dod-recheck` returns FAIL, the implementation completion is revoked.
