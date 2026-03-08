# Plan Review Criteria

12 evaluation viewpoints for `decompose-plan(review)` mode. Task sizing is reviewed through blocker-based `Task Shape Findings`, not numeric granularity scores.

## 1. Forward Fidelity

**Definition**: Every design atom (`REQxx`, `ACxx`, `GOALxx`, `DECxx`) maps to at least one task.

**Check Method**: Compare the design atom index and trace pack against task `Satisfied Requirements` / `Design Anchors`. Confirm every implementable atom appears in at least one task.

**Blocker**: Any `REQxx` or `ACxx` with zero task coverage.

## 2. Reverse Fidelity

**Definition**: Every task maps back to valid design atoms with no orphan work.

**Check Method**: Read each task's anchors and goal, then reconstruct the claimed behavior. Confirm the reconstructed behavior exists in the design and is not just task-local invention.

**Blocker**: Orphan task with no valid design atom anchors.

## 3. Round-trip

**Definition**: The scope reconstructed from tasks matches the original design scope.

**Check Method**: Use `plan.compose.md` as the primary evidence. Treat `missing`, `extra`, or behavior-changing `ambiguous` items as failures unless the draft explains the discrepancy.

**Blocker**: Missing or extra scope items that change functional behavior.

## 4. Behavioral Lock

**Definition**: Lock atoms have both negative executable checks and positive closure checks.

**Check Method**: Inspect lock-bearing requirements and their owner tasks. Confirm each lock has an executable negative check and at least one positive boundary/closure check when the replacement crosses a runtime boundary.

**Blocker**:
- Lock atom with no executable negative check.
- Lock atom represented only by prose.
- Runtime-boundary replacement scope with no positive boundary or closure verification.

## 5. Negative Path

**Definition**: ACs with EARS Type=Unwanted or lock semantics have explicit failure-path coverage.

**Check Method**: Enumerate unwanted/lock ACs from the design and verify each is represented by a RED/DoD failure check in the owning task.

**Blocker**: Unwanted/lock AC with zero negative test coverage.

## 6. Temporal

**Definition**: Every `TEMPxx` has lifecycle coverage and a closure path.

**Check Method**: Read the temporary mechanism trace and closure summary. Confirm each `TEMPxx` has introduction, migration/cutover, and retirement evidence or an explicit waiver.

**Blocker**: Missing `TEMPxx` closure tuple fields, or `TEMPxx` with no introducing/retiring task and no waiver.

## 7. Traceability

**Definition**: Design Anchors and Satisfied Requirements are correctly populated and valid.

**Check Method**: Validate anchor IDs against the design atom index and Decision Trace. Reject prose-only anchors or `TEMPxx` anchors in `plan.md`.

**Blocker**: Invalid or non-existent design atom references, or `TEMPxx` used as a task anchor in `plan.md`.

## 8. Scope

**Definition**: No task implements a non-goal, and `Scope Contract` clearly expresses ownership boundaries.

**Check Method**: Compare each task's goal and `Scope Contract` against `Non-Goals`, compose diff, and neighboring task boundaries. Confirm ownership is explicit and closed-world.

**Blocker**:
- Task explicitly implements a documented non-goal.
- `Owned Paths` missing.
- `Scope Contract` is too broad to communicate ownership.
- `Prohibited Paths` are contradicted by the task's own stated objective.

## 9. Testability

**Definition**: `RED`, `GREEN`, `REFACTOR`, and `DoD` are defined, and RED is an executable failure.

**Check Method**: Read each task contract directly. Confirm RED is executable, verification commands are concrete, and DoD is strict-AND rather than optional prose.

**Blocker**:
- Task missing any of `RED` / `GREEN` / `REFACTOR` / `DoD`.
- RED that is a compile/import error instead of an assertion/runtime failure.
- DoD written as alternatives instead of strict AND conditions.

## 10. Execution Readiness

**Definition**: Verification commands are specific and runnable; shared/project-wide checks are not repeated as boilerplate.

**Check Method**: Spot-check commands for concrete targets and installed tools, then inspect task structure for legacy fields or duplicated risk boilerplate.

**Blocker**:
- Verification command references an unknown tool or an obviously missing file.
- Shared Touchpoint is missing rationale.
- Task still uses legacy `Files`, `Allowed Files`, or `Exception Files`.
- Task still depends on legacy risk/adversarial DoD boilerplate instead of `Risk Tier`.

## 11. Integration Coverage

**Definition**: Cross-task boundaries are validated by at least one real product-path verification surface.

**Check Method**: Follow dependency edges and runtime/public boundaries. Confirm at least one spanning task uses real boundary verification rather than harness-only or mock-only checks.

**Blocker**:
- Cross-task boundary with no boundary-level verification.
- Critical/Sensitive public/runtime task with no real product-path verification.
- Stub-only verification closing a Critical/Sensitive boundary task.

## 12. Risk Classification Consistency

**Definition**: Task `Risk Tier` values are present and consistent with the intended verification surfaces.

**Check Method**: Read task-level `Risk Tier`, changed boundaries, and verification surfaces together. Sensitive/Critical tasks must expose boundary verification, not just local unit success.

**Blocker**:
- Missing or invalid task-level `Risk Tier`.
- Sensitive/Critical task missing `Boundary Verification`.
- Risk tier implies product/public/runtime exposure but the task closes only on local unit verification.

## Task Shape Blockers

Record blocker/warning/info findings using these fixed predicates:

- `MULTI_OBJECTIVE`: a task contains two or more independently releasable objectives.
- `BOUNDARY_WITHOUT_VERIFICATION`: a task spans multiple ownership boundaries without corresponding `Boundary Verification` or `Closure Verification`.
- `RUNTIME_PATH_WITHOUT_REAL_CHECK`: a Critical/Sensitive public/runtime task lacks real product-path verification.
- `OWNERSHIP_TOO_BROAD`: `Owned Paths` are so broad that rollback or ownership is unclear.
- `HARNESS_ONLY_CLOSURE`: the task shape hides boundary closure behind local scaffolding, harness-only assertions, or mock-only verification.
