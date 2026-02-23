# Plan Templates

Templates for `plan.md` output artifact.

## Core Header Template

```markdown
# [Feature] Implementation Plan

**Source**: `docs/plans/YYYY-MM-DD-<topic>-design.md`
**Trace Pack**: `docs/plans/YYYY-MM-DD-<topic>-plan.trace.md`
**Compose Pack**: `docs/plans/YYYY-MM-DD-<topic>-plan.compose.md`
**Goal**: [One-sentence end state]
**Architecture**: [2-3 sentences]
**Tech Stack**: [Key technologies]
```

## Checkpoint Summary Template

```markdown
## Checkpoint Summary

- Alignment Verdict: PASS | FAIL
- Forward Fidelity: PASS | FAIL
- Reverse Fidelity: PASS | FAIL
- Non-Goal Guard: PASS | FAIL
- Granularity Guard: PASS | FAIL
- Trace Pack: `docs/plans/YYYY-MM-DD-<topic>-plan.trace.md`
- Compose Pack: `docs/plans/YYYY-MM-DD-<topic>-plan.compose.md`
- Updated At: `YYYY-MM-DD`
```

## Task Template

Use this structure for every task.

```markdown
### Task N: [Short Title]

**Satisfied Requirements**: [REQxx/ACxx IDs from design doc]
**Design Anchors**: [GOAL/REQ/AC/DEC IDs this task realizes]
**Goal**: [Why this task exists, 1-2 sentences]
**Dependencies**: [Task IDs or `none`]

**Files:**
- Create: `path/from/project/root.ext` (purpose)
- Modify: `path/from/project/root.ext` (purpose)

**RED**
- [Failing test intent]
- Run: `[exact test command]`
- Expected: `FAIL with [error pattern]`

**GREEN**
- [Minimal implementation intent to pass RED]

**REFACTOR**
- [Safe cleanup after GREEN]

**DoD**
- [Verifiable completion criterion]
- [Behavior/contract check tied to requirement IDs]
- Run: `[exact verification command]`
- Expected: `PASS`
```
