<!-- do not edit: generated from skills/src/decompose-plan/references/plan-templates.md.tmpl; edit source and rebuild -->

# Plan Templates

Templates for `plan.md` output artifact.

## Core Header Template

```markdown
# [Feature] Implementation Plan

- **Source**: `docs/plans/<topic>/design.md`
- **Trace Pack**: `docs/plans/<topic>/plan.trace.md`
- **Compose Pack**: `docs/plans/<topic>/plan.compose.md`
- **Goal**: [One-sentence end state]
- **Architecture**: [2-3 sentences]
- **Tech Stack**: [Key technologies]

## Quality Gates

Project-wide checks that every implementation task must satisfy.

| Category    | Command                     |
|-------------|-----------------------------|
| [test]      | `[exact test command]`      |
| [lint]      | `[exact lint command]`      |
| [format]    | `[exact format command]`    |
| [typecheck] | `[exact typecheck command]` |
```

## Checkpoint Summary Template

```markdown
## Checkpoint Summary

- Alignment Verdict: PASS | FAIL
- Scope Contract Guard: PASS | FAIL
- Quality Gate Guard: PASS | FAIL
- Review Artifact: `docs/plans/<topic>/plan.review.md`
- Trace Pack: `docs/plans/<topic>/plan.trace.md`
- Compose Pack: `docs/plans/<topic>/plan.compose.md`
- Updated At: `YYYY-MM-DD`
```

## Task Template

Use this structure for every task.

```markdown
### Task N: [Short Title]

- **Satisfied Requirements**: [REQxx/ACxx IDs from design doc]
- **Design Anchors**: [GOAL/REQ/AC/DEC IDs this task realizes]
- **Goal**: [Why this task exists, 1-2 sentences; one primary objective]
- **Dependencies**: [Task IDs or `none`]
- **Risk Tier**: Standard | Sensitive | Critical

**Scope Contract**:
- **Owned Paths**:
  - `path/to/owned-area/**`
- **Shared Touchpoints**:
  - `path/to/shared-file.ext` (shared configuration or dependency update required by this task)
- **Prohibited Paths**:
  - `path/to/prohibited-area/**`

**RED**
- [Failing test intent]
- Run: `[exact test command]`
- Expected: `FAIL with executable assertion/runtime evidence`

**GREEN**
- [Minimal implementation intent to pass RED]

**REFACTOR**
- [Safe cleanup after GREEN]

**Boundary Verification**:
- Run: `[exact integration/contract/CLI command when the task crosses public/runtime boundaries]`
- Expected: `PASS`

**Closure Verification**:
- Run: `[exact command only when additional closure evidence is required]`
- Expected: `PASS`

**DoD**
- All DoD items are mandatory AND conditions.
- [Verifiable completion criterion]
- [Behavior/contract check tied to requirement IDs]
- [Negative verification for replacement/removal/no-fallback/fail-closed requirements when applicable]
- `Global Quality Gates apply.`
- Run: `[exact verification command]`
- Expected: `PASS`
```

Notes:
- `Boundary Verification` is required when the task crosses public/runtime/integration boundaries.
- `Closure Verification` is optional; use it only when task completion needs an additional explicit close-out surface.
- Do not use `Files`, `Allowed Files`, or `Exception Files`.
