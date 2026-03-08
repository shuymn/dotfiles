---
name: completion-audit
description: Audits product completion after task-level PASS artifacts exist. Use when the plan or Ralph story metadata marks a completion gate for a public CLI/API/runtime/release claim; otherwise it is optional.
---

<!-- do not edit: generated from skills/src/completion-audit/SKILL.md; edit source and rebuild -->


## Path Resolution

- `<skill-root>` means the directory containing this `SKILL.md`.
- Resolve referenced files relative to the project root or `<skill-root>` as appropriate.

# Completion Audit

Run a final product-level audit after task implementation, dod-recheck, and adversarial verification have finished.

## When to Use

- Run this skill when any of the following is true:
  - the plan explicitly claims completion for a public CLI, API, runtime path, or release surface
  - `setup-ralph` propagated `completion_gate: true` for the plan or target story
  - the user explicitly asks for a final completion audit
- Otherwise the skill is optional and should not be inserted automatically.
- Task-level artifacts must already exist; this is a closure gate, not a replacement for implement/recheck/adversarial steps.

## Inputs

- `plan.md`
- `plan.review.md`
- task-level implement / dod-recheck / adversarial artifacts
- current HEAD

## Procedure

1. Read `plan.md` and confirm whether a completion audit is required by plan scope or propagated story metadata.
2. Verify `plan.review.md` is PASS.
3. Verify task-level artifacts are present and fresh for the current task contracts.
4. Run real product-path smoke checks for public/runtime boundaries.
5. Detect off-boundary drift after task completion.
6. Detect stale artifacts or reopened completion gaps.
7. Confirm every AC owner task has closure evidence, not just local PASS.
8. If live integration is explicitly defined by the plan, run it only when the plan marks it opt-in and the environment is available.
9. Write `completion.audit.md`.

## Output Format

```markdown
# <Topic> Completion Audit

## Audit Metadata

- **Source Artifact**: [plan path]
- **Reviewed At**: [timestamp]
- **Overall Verdict**: PASS | FAIL

## Product-Path Smoke

| # | Surface | Command | Exit Code | Verdict | Evidence |
|---|---------|---------|-----------|---------|----------|
| 1 | [cli/api/runtime] | [command] | [code] | PASS/FAIL | [evidence] |

## Open Completion Gaps

| # | Area | Gap | Required Re-run |
|---|------|-----|-----------------|
| 1 | [boundary/artifact/ac-owner] | [description] | [dod-recheck/adversarial/completion-audit] |

## Decision

- Completion claim: confirmed/revoked
- Reason: [rationale]
```

## Stop Conditions

Stop and report failure when:

- required task-level artifacts are missing or stale
- public/runtime smoke cannot be executed as defined by the plan
- off-boundary drift reopens scope or closure
- completion gaps remain unresolved at current HEAD

## Trigger Rule

- **Mandatory**: when the plan or Ralph metadata marks a completion gate for a public CLI/API/runtime/release claim.
- **Optional**: docs-only work, purely local internal refactors, or any plan that does not claim product-surface completion.

## Key Principle

Task completion and product completion are different gates. `completion-audit` exists to verify the latter.
