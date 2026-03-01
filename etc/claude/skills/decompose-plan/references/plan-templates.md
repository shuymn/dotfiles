# Plan Templates

Templates for `plan.md` output artifact.

## Core Header Template

```markdown
# [Feature] Implementation Plan

- **Source**: `docs/plans/YYYY-MM-DD-<topic>-design.md`
- **Trace Pack**: `docs/plans/YYYY-MM-DD-<topic>-plan.trace.md`
- **Compose Pack**: `docs/plans/YYYY-MM-DD-<topic>-plan.compose.md`
- **Goal**: [One-sentence end state]
- **Architecture**: [2-3 sentences]
- **Tech Stack**: [Key technologies]

## Quality Gates

Project-wide checks that every task must pass at DoD.

| Category    | Command                     |
|-------------|-----------------------------|
| [test]      | `[exact test command]`      |
| [lint]      | `[exact lint command]`      |
| [format]    | `[exact format command]`    |
| [typecheck] | `[exact typecheck command]` |

> Omit this section only when Step 1.7 detected no quality gates.
```

## Checkpoint Summary Template

```markdown
## Checkpoint Summary

- Alignment Verdict: PASS | FAIL
- Forward Fidelity: PASS | FAIL
- Reverse Fidelity: PASS | FAIL
- Non-Goal Guard: PASS | FAIL
- Behavioral Lock Guard: PASS | FAIL
- Granularity Guard: PASS | FAIL
- Temporal Completeness Guard: PASS | FAIL
- Quality Gate Guard: PASS | FAIL | N/A (no quality gates detected)
- TEMP Summary: introduced=X, retired=Y, open=Z, waived=W
- Trace Pack: `docs/plans/YYYY-MM-DD-<topic>-plan.trace.md`
- Compose Pack: `docs/plans/YYYY-MM-DD-<topic>-plan.compose.md`
- Updated At: `YYYY-MM-DD`
```

## Task Template

Use this structure for every task.

```markdown
### Task N: [Short Title]

- **Satisfied Requirements**: [REQxx/ACxx IDs from design doc]
- **Design Anchors**: [GOAL/REQ/AC/DEC IDs this task realizes]
- **Goal**: [Why this task exists, 1-2 sentences]
- **Dependencies**: [Task IDs or `none`]

**Files:**
- Create: `path/from/project/root.ext` (purpose)
- Modify: `path/from/project/root.ext` (purpose)

**RED**
- [Failing test intent]
- If referenced implementation symbols/files do not exist yet, add minimal scaffolding so the test compiles and runs.
- If direct unit-level RED is technically difficult, choose the nearest executable boundary test (integration/contract/e2e) while preserving fail-first.
- Run: `[exact test command]`
- Expected: `FAIL with [assertion/runtime error pattern]`
- Note: compilation/import/module errors are not valid RED outcomes.

**GREEN**
- [Minimal implementation intent to pass RED]

**REFACTOR**
- [Safe cleanup after GREEN]

**DoD**
- All DoD items are mandatory AND conditions (never OR).
- [Verifiable completion criterion]
- [Behavior/contract check tied to requirement IDs]
- [Negative verification for replacement/removal/no-fallback/fail-closed requirements when applicable]
- [Boundary-level verification command when scope crosses runtime boundaries]
- Run: `[exact verification command]`
- Expected: `PASS`
- Run: all commands in `## Quality Gates`
- Expected: all `PASS`
> Omit the two lines above when Step 1.7 detected no quality gates.
```
