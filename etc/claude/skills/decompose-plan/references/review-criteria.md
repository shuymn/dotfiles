# Plan Review Criteria

13 evaluation viewpoints for `decompose-plan(review)` mode. Absorbs the former `analyze-plan` audit function.

## 1. Forward Fidelity

**Definition**: Every design atom (`REQxx`, `ACxx`, `GOALxx`, `DECxx`) maps to at least one task.

**Check Method**:
- Build a design atom index from the source design doc.
- Verify every `REQxx` and `ACxx` appears in at least one task's `Satisfied Requirements`.
- Verify every `DECxx` appears in at least one task's `Design Anchors` with a valid `ADR-xxxx` mapping.
- Verify every `GOALxx` is covered by one or more tasks.

**Severity**:
- **Blocker**: Any `REQxx` or `ACxx` with zero task coverage.
- **Warning**: `GOALxx` covered only indirectly (no direct task anchor).

## 2. Reverse Fidelity

**Definition**: Every task maps back to valid design atoms — no orphan tasks.

**Check Method**:
- Verify every task has at least one `REQxx` or `ACxx` in `Satisfied Requirements`.
- Verify every task anchor points to an existing design atom.
- Reconstruct design intent from task `Design Anchors`, `Goal`, `GREEN`, and `DoD`.

**Severity**:
- **Blocker**: Orphan task with no valid design atom anchors.
- **Warning**: Task with valid anchors but unclear mapping rationale.

## 3. Round-trip

**Definition**: The scope reconstructed from tasks matches the original design scope.

**Check Method**:
- Compare reconstructed design summary (from `plan.compose.md`) against source design.
- Check for `missing`, `extra`, or `ambiguous` scope items in the compose diff.

**Severity**:
- **Blocker**: Missing or extra scope items that change functional behavior.
- **Warning**: Ambiguous mappings that could be clarified.

## 4. Behavioral Lock

**Definition**: Lock atoms — design expressions that restrict behavior to a single path, remove/replace an existing capability, or mandate failure on a former path — have both negative and positive executable checks. Common keyword examples (not exhaustive): `only`, `must not`, `remove`, `no fallback`, `fail-closed`.

**Check Method**:
- Extract lock atoms from design wording, ACs, and `Existing Codebase Constraints`.
- For each lock atom, verify at least one negative executable check proving the forbidden path fails.
- For each lock atom, verify at least one positive boundary check proving the new path works.
- For cross-boundary replacements, verify boundary-level commands (not just unit tests).

**Severity**:
- **Blocker**: Lock atom with no executable negative check. Lock atom represented only by prose.
- **Blocker**: Runtime-boundary replacement scope with no boundary-level verification command.

## 5. Negative Path

**Definition**: ACs with EARS Type=Unwanted or lock requirements have explicit negative/failure test coverage.

**Check Method**:
- Identify all ACs with EARS Type=Unwanted.
- Identify all ACs expressing exclusivity, removal, replacement, or mandatory failure on a former path (lock semantics). Common keyword examples (not exhaustive): `only`, `must not`, `remove`, `fail-closed`.
- Verify each has at least one negative test in RED or DoD.

**Severity**:
- **Blocker**: Unwanted/lock AC with zero negative test coverage.

## 6. Granularity

**Definition**: Each task passes hard-gate properties and respects split signals.

**Check Method**:
- Verify hard-gate: single primary objective, single main verification flow, clear rollback boundary.
- Count split signals per task; when 2+ signals, verify task is split or has waiver metadata.
- Flag overly broad, fragmented, or unjustified waived tasks.

**Severity**:
- **Blocker**: Task failing hard-gate properties (multiple objectives, no rollback boundary).
- **Warning**: Task with 2+ split signals and a waiver — check waiver quality.

## 7. Temporal

**Definition**: Every `TEMPxx` has complete lifecycle coverage (introducing, migrating/cutover, retiring).

**Check Method**:
- Verify each `TEMPxx` maps to at least one introducing task and one retiring task in `Temporary Mechanism Trace`.
- Verify retiring task DoD includes negative verification of fallback/temporary-path removal.
- Verify `TEMPxx` in-doc closure summary (checklist/ledger row) has all closure tuple fields.
- Open `TEMPxx` entries are allowed only with explicit waiver metadata.

**Severity**:
- **Blocker**: `TEMPxx` closure missing (retirement trigger, verification, or removal scope). `TEMPxx` without introducing or retiring task and no waiver.
- **Warning**: `TEMPxx` with waiver but vague deadline.

## 8. Traceability

**Definition**: Design Anchors and Satisfied Requirements are correctly populated and valid.

**Check Method**:
- Verify all task anchors reference existing design atom IDs.
- Verify `Satisfied Requirements` use `REQxx`/`ACxx` format (not raw prose).
- Verify `DECxx` anchors map to exactly one `ADR-xxxx` in Decision Trace.
- Verify `TEMPxx` IDs are not used as Design Anchors in `plan.md` (kept in trace only).

**Severity**:
- **Blocker**: Invalid or non-existent design atom references. `TEMPxx` used as task anchor in `plan.md`.

## 9. Scope

**Definition**: No task implements a non-goal, and no scope creep exists.

**Check Method**:
- Verify no task maps to `NONGOALxx`.
- Verify no task introduces behavior outside mapped design atoms.
- Cross-check against compose pack for `extra` items.

**Severity**:
- **Blocker**: Task explicitly implementing a documented non-goal.
- **Warning**: Task with behavior not clearly anchored to design atoms.

## 10. Testability

**Definition**: RED/GREEN/REFACTOR/DoD are defined, and RED is an executable failure.

**Check Method**:
- Verify every task defines `RED`, `GREEN`, `REFACTOR`, and `DoD`.
- Verify RED describes executable failing tests (not compile/import errors).
- Verify DoD items are written as AND semantics (all mandatory, no OR wording).
- Verify verification commands are concrete and runnable.

**Severity**:
- **Blocker**: Task missing any of RED/GREEN/REFACTOR/DoD. RED that is a compile error, not an assertion failure.
- **Warning**: Verification command that is concrete but may need environment setup.

## 11. Execution Readiness

**Definition**: Verification commands are specific, concrete, and executable.

**Check Method**:
- Verify each task's verification commands reference specific files, modules, or endpoints.
- Flag missing/unclear commands, unknown tools, or undocumented environment assumptions.
- Verify Quality Gate references are present in every task DoD.

**Severity**:
- **Blocker**: Verification command referencing unknown tool or missing file. Quality Gate reference missing in any task DoD.
- **Warning**: Command that is valid but could be more specific.

## 12. Integration Coverage

**Definition**: Cross-task dependency boundaries are validated by at least one boundary-level test (integration/contract/e2e).

**Check Method**:
- Identify cross-task boundaries where a task depends on another task (`**Dependencies**` references).
- For each boundary, verify at least one spanning task includes boundary-level verification in RED or DoD.
- If no dependency edges exist, mark this viewpoint as `N/A` with explanation.

**Severity**:
- **Blocker**: Any cross-task boundary with no boundary-level test coverage.
- **Info**: N/A when no dependency edges exist.

## 13. Risk Classification Consistency

**Definition**: Task risk tiers are consistent with the design doc's `## Risk Classification` and tier-specific DoD requirements are present.

**Check Method**:
- Verify each task's `Risk Tier` field matches the highest tier from the design doc's Risk Classification for its change targets.
- Verify Critical tasks include `Adversarial verification required (minimum 3 probes).` in DoD.
- Verify Sensitive tasks include `Heightened dod-recheck scrutiny applies` in DoD.
- Verify Sensitive tasks include `Lightweight adversarial verification required (minimum 2 probes: Category 1 + most relevant 1 category).` in DoD.

**Severity**:
- **Blocker**: Task touching a Critical-classified area but assigned Standard tier. Critical task missing adversarial verification DoD requirement. Task touching a Sensitive-classified area but assigned Standard tier. Sensitive task missing lightweight adversarial DoD requirement.

## Blocker Conditions Summary

The following conditions are always blockers (inherited from the former `analyze-plan` audit):

- `TEMPxx` closure field missing (retirement trigger, verification, or removal scope)
- Lock atom with no executable negative check
- Cross-task boundary with no boundary-level test (integration/contract/e2e)
- Quality Gate reference missing in any task DoD
- Any `REQxx` or `ACxx` with zero task coverage
- Orphan task with no valid design atom anchors
- Task implementing a documented non-goal
- RED that is a compile/import error instead of an assertion failure
- Critical-area task classified as Standard tier
- Sensitive-area task classified as Standard tier
- Sensitive task missing lightweight adversarial DoD requirement
