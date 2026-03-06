# Design Doc Review Mode

> `<skill-root>` means the directory containing the parent `SKILL.md`. Resolve `scripts/...` and `references/...` relative to `<skill-root>`, not to this file's location.

Independent verification of an approved design document. This mode runs as a sub-agent (`fork_context=false`) in a separate session because the authoring agent cannot reliably catch its own blind spots — confirmation bias makes self-verification unreliable.

## Constraints

- The reviewing agent must NOT have created or edited the design doc being reviewed.
- Do NOT propose architectural changes or scope modifications.
- Do NOT modify the design doc or any other artifact.
- Write only the review report.
- When writing paths or commands into the report, use repository-relative project paths. If you mention a skill helper, render it as `scripts/<name>.sh`, never an absolute filesystem path.

## Input

- Path to an approved design doc (e.g., `docs/plans/<topic>/design.md`)

## Procedure

1. **Generate Header**: Run `<skill-root>/scripts/digest-stamp.sh design-review <design-file>` to produce the review metadata header.
2. **Run Split Checker**: Run `uv run python <skill-root>/scripts/split_check.py <design-file>` and keep both blockers and advisories for evidence.
3. **Load Review Criteria**: Read `<skill-root>/references/review-criteria.md` for the 8 evaluation viewpoints.
4. **Evaluate Each Viewpoint**: For each of the 8 criteria:
   - Assess the design doc against the criterion definition and check method.
   - Record PASS, FAIL, or N/A with specific evidence (section, AC ID, or quote).
   - For `Decomposition Fit`, use `<skill-root>/scripts/split_check.py` output as the authoritative blocker signal.
   - If the split checker reports advisories but no blockers, keep `Decomposition Fit` as `PASS` and move the advisories into `## Improvement Notes`.
5. **Compute Overall Verdict**: `Overall Verdict: PASS` only when ALL 8 viewpoints are PASS (N/A counts as PASS). Any FAIL → `Overall Verdict: FAIL`.
6. **Write Review Report**: Output to `.../design.review.md` (derive path by replacing `design.md` with `design.review.md`).

## Output Format

```markdown
# <Topic> - Design Review

## Review Metadata

<digest-stamp.sh output>
- **Overall Verdict**: PASS | FAIL

## Findings

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Missing Failure Modes | PASS/FAIL | [specific evidence] |
| 2 | Implicit Assumptions | PASS/FAIL | [specific evidence] |
| 3 | AC Testability | PASS/FAIL | [specific evidence] |
| 4 | Inter-AC Contradictions | PASS/FAIL | [specific evidence] |
| 5 | Boundary Gaps | PASS/FAIL | [specific evidence] |
| 6 | Risk Classification Coverage | PASS/FAIL/N/A | [specific evidence] |
| 7 | Goal-AC Coverage | PASS/FAIL | [specific evidence] |
| 8 | Decomposition Fit | PASS/FAIL | [specific evidence, including `<skill-root>/scripts/split_check.py` when relevant] |

## Blocking Issues

- [ ] [Issues that must be fixed — only if Overall Verdict is FAIL]

## Improvement Notes

- [Split-check advisories or non-blocking review notes]

## Decision

- Proceed to `decompose-plan`: yes/no
- Reason: [rationale]
```
