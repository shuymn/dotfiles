# Design Doc Review Criteria

Fixed 6-point evaluation framework for `design-doc(review)` mode.

## 1. Missing Failure Modes

**Definition**: Failure paths, error cases, and degraded-state behaviors that the design does not address.

**Check Method**:
- For each AC, ask: "What happens when this fails?"
- Scan `Detailed Design` for operations that can fail (network calls, file I/O, parsing, auth) without documented failure behavior.
- Check `Existing Codebase Constraints` for error paths in current code not covered by new ACs.

**Severity**:
- **Blocker**: A failure mode that would cause data loss, security breach, or silent corruption.
- **Warning**: A failure mode that would cause poor UX or unclear error messages but no data loss.

## 2. Implicit Assumptions

**Definition**: Unstated preconditions, environmental dependencies, or behavioral expectations that the design relies on without documenting.

**Check Method**:
- Identify external dependencies (APIs, databases, file systems, other services) and verify assumptions are documented.
- Check if `Clarifications` section covers all assumption-prone areas.
- Look for language that treats an assumption as self-evident or universally shared without stating it explicitly — this signals an undocumented precondition. Common examples (not exhaustive): "obviously", "naturally", "of course", "clearly", "当然", "もちろん", "言うまでもなく".
- Verify environment requirements (OS, runtime versions, available tools) are stated when non-trivial.

**Severity**:
- **Blocker**: An assumption that, if wrong, would invalidate a core design decision or make an AC unverifiable.
- **Warning**: An assumption that, if wrong, would require minor adjustments but not redesign.

## 3. AC Testability

**Definition**: Whether each Acceptance Criterion's Verification Intent is executable, unambiguous, and produces a deterministic PASS/FAIL result.

**Check Method**:
- For each AC, verify:
  - The Verification Intent specifies a concrete method (command, test, observable behavior).
  - The expected outcome is objectively measurable (not "works correctly" or "performs well").
  - The verification can be performed by someone with no design context (self-contained).
- Flag ACs whose verification cannot produce a deterministic PASS/FAIL without subjective interpretation. Look for qualitative judgments, undefined thresholds, relative terms, and vague verbs regardless of language.
  - Common examples (not exhaustive): `appropriate`, `reasonable`, `adequate`, `sufficient`, `timely`, `properly`, `correctly`, `as needed`, `if possible`, `適切な`, `十分な`, `適宜`, `必要に応じて`, `正しく`, `それなりの`, `しかるべき`.

**Severity**:
- **Blocker**: An AC whose verification cannot produce a deterministic PASS/FAIL.
- **Warning**: An AC that is testable but requires clarification of boundary values or thresholds.

## 4. Inter-AC Contradictions

**Definition**: Conflicts or logical incompatibilities between two or more Acceptance Criteria.

**Check Method**:
- Cross-reference ACs pairwise for contradictory requirements (e.g., "must always X" vs. "when Y, must not X").
- Check for conflicting EARS types applied to the same system behavior.
- Verify that error-handling ACs (Unwanted type) do not contradict normal-flow ACs (Event-Driven/Ubiquitous).
- Check Non-Goals against ACs to ensure no AC implements a non-goal.

**Severity**:
- **Blocker**: Two ACs that cannot both be satisfied simultaneously.
- **Warning**: ACs that appear to overlap in scope with unclear priority.

## 5. Boundary Gaps

**Definition**: Missing edge cases, boundary values, and limit conditions that the design does not specify.

**Check Method**:
- For each AC with numeric thresholds or ranges, verify boundary values are specified (min, max, zero, empty, overflow).
- For each AC with collection/list inputs, verify behavior for empty, single-element, and large collections.
- For each AC with string inputs, verify behavior for empty string, whitespace-only, and max-length.
- For state transitions, verify all entry/exit conditions and invalid state transitions.
- For time-dependent behavior, verify timeout values, retry limits, and concurrent access.

**Severity**:
- **Blocker**: A missing boundary that could cause runtime errors, panics, or undefined behavior.
- **Warning**: A missing boundary that would cause degraded behavior but not failure.

## 6. Risk Classification Coverage

**Definition**: Risk tier is consistent with the actual change scope of the design, and Standard entries have a credible semantic justification.

**Check Method**:
- For each Standard row in `## Risk Classification`, verify the Change Rationale contains the format `Not Critical: [reason] / Not Sensitive: [reason]`.
- Verify the justification is consistent with the design content (Detailed Design, Existing Codebase Constraints, Acceptance Criteria) — flag any direct contradiction.
- Check whether areas touching external interfaces, state management, or failure-sensitive paths are under-classified as Standard.
- ACs that include prohibited-path/allowed-path semantics, data integrity requirements, or error-handling for coordinated rollback scenarios are evidence of Sensitive or higher tier — flag Standard classification in those areas.

**Severity**:
- **Blocker**: Justification absent from a Standard entry / design content directly contradicts the Standard justification.
- **Warning**: Justification is generic (repeats tier definition verbatim without area-specific reasoning) / borderline area lacks explicit rationale. To distinguish: a generic justification restates the tier definition with no area-specific detail (e.g., "Not Critical: defect would not cause irreversible damage / Not Sensitive: defect would not silently corrupt state" — this says nothing specific about the area). An acceptable justification names concrete characteristics of the area (e.g., "Not Critical: read-only display component with no write paths or auth logic / Not Sensitive: UI-only change, no state management or API contract involved").

**N/A Condition**: Greenfield design (no `## Risk Classification` section present).
