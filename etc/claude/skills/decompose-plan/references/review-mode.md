# Plan Review Mode

> All paths in this file (e.g., `scripts/`, `references/`) are relative to the skill root directory, not to this file's location.

Independent verification of an approved plan bundle. This mode runs as a sub-agent (`fork_context=false`) in a separate session because the planning agent cannot reliably catch its own blind spots — confirmation bias makes self-verification unreliable.

## Constraints

- The reviewing agent must NOT have created the plan being reviewed.
- Do NOT modify the plan, design doc, or `scripts/review_finalize.py`.
- Do NOT edit the final review artifact by hand; let the finalizer generate it.
- Write only the review draft report; the final gate artifact is produced by a script.
- Do NOT read `scripts/review_finalize.py` or inspect its constants.
- Do NOT compute granularity totals, thresholds, PASS/FAIL, or `Overall Verdict` yourself.

## Input

- Plan bundle path (e.g., `docs/plans/<topic>/plan.md` + sidecars)
- Source design doc path

## Procedure

1. **Design Review Gate Re-check**: Run `scripts/gate-check.sh <design.review.md> <design.md>` to confirm the design review is still valid. If FAIL, stop immediately.
2. **Structural Check**: Run `scripts/structural-check.sh <design-file> <plan-file>` and keep the result for evidence. The finalizer will re-run it and make it authoritative.
3. **Semantic Verification**: Load `references/review-criteria.md` and `references/granularity-poker.md`.
4. **Write Draft Review**: Output reviewer findings to `.../plan.review.draft.md` (derive path by replacing `plan.md` with `plan.review.draft.md`).
5. **Finalize Review**: Run `uv run python scripts/review_finalize.py <plan-file> <draft-file> <final-file>` where `<final-file>` is `.../plan.review.md`.
6. **Use Only Final Artifact for Gates**: Downstream skills and gate checks must consume `plan.review.md`, never `plan.review.draft.md`.

## Draft Output Format

```markdown
# <Topic> - Plan Review Draft

## Reviewer Summary

- Forward Fidelity: PASS | FAIL
- Reverse Fidelity: PASS | FAIL
- Round-trip: PASS | FAIL
- Behavioral Lock: PASS | FAIL
- Negative Path: PASS | FAIL
- Temporal: PASS | FAIL
- Traceability: PASS | FAIL
- Scope: PASS | FAIL
- Testability: PASS | FAIL
- Execution Readiness: PASS | FAIL
- Integration Coverage: PASS | FAIL | N/A (no cross-task deps)
- Risk Classification: PASS | FAIL | N/A (greenfield without Critical-domain changes)

## Granularity Poker

| Task | Objective | Surface | Verification | Rollback | Evidence |
|------|-----------|---------|--------------|----------|----------|
| Task 1 | 2 | 3 | 2 | 1 | [evidence tied to plan fields] |

## Findings

| ID | Severity | Area | File/Section | Issue | Action |
|----|----------|------|--------------|-------|--------|
| R1 | blocker/warn/info | [viewpoint] | [location] | [issue] | [action] |

## Blocking Issues

- [ ] [Issues that must be fixed]

## Non-Blocking Improvements

- [Suggestions]

## Decision

- Proceed to `execute-plan`: pending machine finalization
- Reason: [rationale]
```

## Final Artifact Notes

- The finalizer script generates `plan.review.md`.
- `plan.review.md` includes `## Review Metadata`, `## Summary`, `## Granularity Gate (Machine)`, and `## Decision`.
- `Granularity` and `Overall Verdict` are machine-computed from the draft content; do not write them into the draft.
