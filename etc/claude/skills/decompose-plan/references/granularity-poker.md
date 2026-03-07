# Granularity Poker

Review-only scoring rubric for `decompose-plan review`.

## Constraints

- Score every task in `plan.md`.
- Use only cards `1`, `2`, `3`, `5`, or `8`.
- Fill one row per task in `## Granularity Poker`.
- Do not total the cards.
- Do not assign PASS/FAIL.
- Do not mention thresholds.
- Do not read the `skit review-finalize` source code or inspect its constants.
- If uncertain between two cards, choose the smaller plausible card and note the ambiguity in `Evidence`.

## Output Table

```markdown
## Granularity Poker

| Task | Objective | Surface | Verification | Rollback | Evidence |
|------|-----------|---------|--------------|----------|----------|
| Task 1 | 2 | 3 | 2 | 1 | Goal is single-path; DoD has one boundary command; files stay within `src/foo/**`. |
```

## Axis Guide

### Objective

- `1`: One narrow behavior change with no independently releasable sub-outcome.
- `2`: One behavior change with small adjacent cleanup or test scaffolding.
- `3`: One user/system outcome with moderate branching in the same slice.
- `5`: One outcome plus tightly-coupled sub-behaviors that could plausibly be split.
- `8`: More than one independently releasable objective.

### Surface

- `1`: One local implementation area.
- `2`: One area plus adjacent tests/config in the same boundary.
- `3`: One component boundary plus a close collaborator.
- `5`: Multiple top-level path families or components that could be separated.
- `8`: Unrelated domains or ownership boundaries.

### Verification

- `1`: One verification command in one harness.
- `2`: One main command plus a nearby supporting check.
- `3`: One main flow plus one explicit boundary confirmation.
- `5`: Two independent verification flows, environments, or command families.
- `8`: Three or more independent flows or staged validation across boundaries.

### Rollback

- `1`: Clean isolated rollback with obvious file reversion.
- `2`: Local rollback with minor adjacent follow-up.
- `3`: Rollback stays possible but crosses a nearby contract/helper seam.
- `5`: Partial rollback risk or coupled cutover behavior.
- `8`: Cannot be cleanly rolled back in isolation.

## Evidence Rules

- Prefer citing `Goal`, `Dependencies`, `Files`, `Allowed Files`, `RED`, and `DoD`.
- Mention the concrete field names or commands that drove the card choice.
- Keep evidence to one short sentence per task row.
