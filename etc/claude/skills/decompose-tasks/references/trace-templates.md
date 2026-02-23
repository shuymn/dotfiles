# Trace & Check Templates

Templates for `plan.trace.md` and `plan.compose.md` output artifacts.

## Trace Matrix Templates (for `plan.trace.md`)

```markdown
## Decision Trace
- DEC01 -> ADR-0007
- DEC02 -> ADR-0014

## Design -> Task Trace Matrix
- [REQxx]: Task A, Task B
- [ACxx]: Task C
- [GOALxx]: Task A, Task D
- [DECxx (ADR-xxxx)]: Task E

## Task -> Design Compose Matrix
- Task A: REQxx, ACxx, GOALxx
- Task B: REQyy, DECzz
```

## Cross Self-Check Template (for `plan.trace.md`)

```markdown
## Cross Self-Check

### Forward Fidelity (Design -> Tasks)
- Coverage ratio (`REQ+AC covered / total REQ+AC`): `X/Y`
- Coverage ratio (`DEC covered / total DEC`): `X/Y`
- Invalid DEC-to-ADR mappings: [if any]
- Missing design atoms: [if any]

### Reverse Fidelity (Tasks -> Design)
- Orphan tasks (no valid anchors): [if any]
- Tasks missing `REQxx/ACxx` in `Satisfied Requirements`: [if any]
- Alignment verdict: PASS | FAIL
- Gaps and actions: [If FAIL, list fixes and update tasks]

### Non-Goal Guard
- Violations against `NONGOALxx`: [if any]

### Granularity Guard
- Tasks too broad for a single coherent change unit: [if any]
- Tasks too fragmented (should be merged): [if any]
```

## Compose Reconstruction Template (for `plan.compose.md`)

```markdown
## Compose Reconstruction

### Reconstructed Design Summary
- [3-7 bullets]

### Scope Diff
- Missing from tasks: [if any]
- Extra in tasks: [if any]
- Ambiguous mappings: [if any]

### Alignment Verdict
- PASS | FAIL
- Required fixes: [if FAIL]
```
