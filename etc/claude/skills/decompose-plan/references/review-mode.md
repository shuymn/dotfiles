# Plan Review Mode

> All paths in this file (e.g., `scripts/`, `references/`) are relative to the skill root directory, not to this file's location.

Independent verification of an approved plan bundle. This mode runs as a sub-agent (`fork_context=false`) in a separate session because the planning agent cannot reliably catch its own blind spots — confirmation bias makes self-verification unreliable.

## Constraints

- The reviewing agent must NOT have created the plan being reviewed.
- Do NOT modify the plan, design doc, or any other artifact.
- Write only the review report.

## Input

- Plan bundle path (`...-plan.md` + sidecars)
- Source design doc path

## Procedure

1. **Design Review Gate Re-check**: Run `scripts/gate-check.sh <design.review.md> <design.md>` to confirm the design review is still valid. If FAIL, stop immediately.
2. **Structural Check**: Run `scripts/structural-check.sh <design-file> <plan-file>`. If any structural check fails, mark `Overall Verdict: FAIL` immediately.
3. **Generate Header**: Run `scripts/digest-stamp.sh plan-review <plan-file>` to produce the review metadata header.
4. **Semantic Verification**: Load `references/review-criteria.md` and evaluate all 11 viewpoints against the plan bundle and source design.
5. **Record Findings**: For each viewpoint, record PASS or FAIL with specific evidence.
6. **Compute Overall Verdict**: `Overall Verdict: PASS` only when ALL viewpoints are PASS. Any FAIL → `Overall Verdict: FAIL`.
7. **Write Review Report**: Output to `...-plan.review.md` (derive path by replacing `-plan.md` with `-plan.review.md`).

## Output Format

```markdown
# <Topic> - Plan Review

## Review Metadata

<digest-stamp.sh output>
- **Overall Verdict**: PASS | FAIL

## Summary

- Forward Fidelity: PASS | FAIL
- Reverse Fidelity: PASS | FAIL
- Round-trip: PASS | FAIL
- Behavioral Lock: PASS | FAIL
- Negative Path: PASS | FAIL
- Granularity: PASS | FAIL
- Temporal: PASS | FAIL
- Traceability: PASS | FAIL
- Scope: PASS | FAIL
- Testability: PASS | FAIL
- Execution Readiness: PASS | FAIL
- Updated At: YYYY-MM-DD HH:MM TZ

## Findings

| ID | Severity | Area | File/Section | Issue | Action |
|----|----------|------|--------------|-------|--------|
| R1 | blocker/warn/info | [viewpoint] | [location] | [issue] | [action] |

## Blocking Issues

- [ ] [Issues that must be fixed — only if Overall Verdict is FAIL]

## Non-Blocking Improvements

- [Suggestions]

## Decision

- Proceed to `execute-plan`: yes/no
- Reason: [rationale]
```
