# Design Doc Review Mode

> All paths in this file (e.g., `scripts/`, `references/`) are relative to the skill root directory, not to this file's location.

Independent verification of an approved design document. This mode runs as a sub-agent (`fork_context=false`) in a separate session because the authoring agent cannot reliably catch its own blind spots — confirmation bias makes self-verification unreliable.

## Constraints

- The reviewing agent must NOT have created or edited the design doc being reviewed.
- Do NOT propose architectural changes or scope modifications.
- Do NOT modify the design doc or any other artifact.
- Write only the review report.

## Input

- Path to an approved design doc (e.g., `docs/plans/YYYY-MM-DD-<topic>-design.md`)

## Procedure

1. **Generate Header**: Run `scripts/digest-stamp.sh design-review <design-file>` to produce the review metadata header.
2. **Load Review Criteria**: Read `references/review-criteria.md` for the 5 evaluation viewpoints.
3. **Evaluate Each Viewpoint**: For each of the 5 criteria:
   - Assess the design doc against the criterion definition and check method.
   - Record PASS or FAIL with specific evidence (section, AC ID, or quote).
4. **Compute Overall Verdict**: `Overall Verdict: PASS` only when ALL 5 viewpoints are PASS. Any FAIL → `Overall Verdict: FAIL`.
5. **Write Review Report**: Output to `...-design.review.md` (derive path by replacing `-design.md` with `-design.review.md`).

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

## Blocking Issues

- [ ] [Issues that must be fixed — only if Overall Verdict is FAIL]

## Decision

- Proceed to `decompose-plan`: yes/no
- Reason: [rationale]
```
