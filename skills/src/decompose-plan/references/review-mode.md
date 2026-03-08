# Plan Review Mode

> `<skill-root>` means the directory containing the parent `SKILL.md`. Resolve `scripts/...` and `references/...` relative to `<skill-root>`, not to this file's location.

Independent verification of an approved plan bundle. This mode runs as a sub-agent (`fork_context=false`) in a separate session because the planning agent cannot reliably catch its own blind spots.

## Constraints

- The reviewing agent must NOT have created the plan being reviewed.
- Do NOT modify the plan or design doc.
- Do NOT edit the final review artifact by hand; let the finalizer generate it.
- Write only the review draft report; the final gate artifact is produced by a script.
- Do NOT inspect the internals of `skit review-finalize` or its constants.
- Do NOT compute numeric granularity scores, totals, or machine verdicts.
- When writing paths or commands into the draft, use repository-relative project paths. If you mention a skill helper, render it as `scripts/<name>.sh`, never an absolute filesystem path.

## Input

- Plan bundle path (for example `docs/plans/<topic>/plan.md` + sidecars)
- Source design doc path

## Procedure

1. **Design Review Gate Re-check**: Run `skit gate-check <review-file> <source-file>` to confirm the design review is still valid. If FAIL, stop immediately.
2. **Structural Check**: Run `skit structural-check <design-file> <plan-file>` and keep the result for evidence. The finalizer re-runs it and makes it authoritative.
3. **Semantic Verification**: Load `<skill-root>/references/review-criteria.md`.
4. **Write Draft Review**: Output reviewer findings to `.../plan.review.draft.md` (derive path by replacing `plan.md` with `plan.review.draft.md`).
5. **Finalize Review**: Run `skit review-finalize <plan-file> <draft-file> <final-file>` where `<final-file>` is `.../plan.review.md`.
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

## Task Shape Findings

| Task | Severity | Predicate | Evidence | Action |
|------|----------|-----------|----------|--------|
| Task 1 | blocker/warning/info | [MULTI_OBJECTIVE \| BOUNDARY_WITHOUT_VERIFICATION \| RUNTIME_PATH_WITHOUT_REAL_CHECK \| OWNERSHIP_TOO_BROAD \| HARNESS_ONLY_CLOSURE] | [plan evidence tied to task fields] | [action] |

## Findings

| ID | Severity | Area | File/Section | Issue | Action |
|----|----------|------|--------------|-------|--------|
| R1 | blocker/warn/info | [viewpoint] | [location] | [issue] | [action] |

## Blocking Issues

- [ ] [Issues that must be fixed]

## Non-Blocking Improvements

- [Suggestions]

## Decision

- Proceed to `execute-plan`: pending finalization
- Reason: [rationale]
```

## Final Artifact Notes

- The finalizer script generates `plan.review.md`.
- `plan.review.md` includes `## Review Metadata`, `## Summary`, `## Task Shape Findings`, and `## Decision`.
- `Overall Verdict` is finalized from structural checks, summary viewpoints, and the absence of task-shape blockers.
- `Task Shape Findings` are blocker-based. They do not use numeric granularity scores, and `Predicate` must use the fixed vocabulary above.
