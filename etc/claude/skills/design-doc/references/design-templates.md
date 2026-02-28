# Design Doc Templates

## Design Doc Template

Use this structure as a starting point. Adapt sections as needed for the specific topic — not every section is required for every design.

```markdown
# <Topic> - Design

## Overview

[1-2 paragraphs summarizing what this design covers and why]

## Goals

- [What this design aims to achieve]

## Non-Goals

- [What is explicitly out of scope]

## Background

[Context needed to understand this design. Prior art, related systems, constraints.]

## Clarifications

| Question | Answer / Assumption | Impact | Status |
|----------|----------------------|--------|--------|
| [What needed clarification] | [Final answer or explicit assumption] | [How design/scope changes] | resolved / assumed |

## Decomposition Strategy

- Split Decision: single | root-sub
- Decision Basis: [Which contract conditions triggered this decision]
- Root Scope: [Global responsibilities and integration-only responsibilities]

### Sub-Doc Index (required when root-sub)

| Sub ID | File | Owned Boundary | Owns Requirements/AC |
|--------|------|----------------|----------------------|
| SUB-A | docs/plans/YYYY-MM-DD-<topic>-sub-a-design.md | [boundary] | [ID ranges or summary] |

### Root Coverage (required when root-sub)

| Root Requirement/AC | Covered By (Sub ID or Integration) | Notes |
|---------------------|------------------------------------|-------|
| [ROOT-REQ/ROOT-AC] | [SUB-A / Integration] | [mapping rationale] |

## Design

[Main design content. Organize into subsections appropriate for the topic.]

### [Subsection as needed]

[Use diagrams (Mermaid preferred over ASCII art) where they add clarity.]

## Compatibility & Sunset

[Required for breaking changes or staged migrations.]

### Temporary Mechanism Ledger

| ID | Mechanism | Introduced For | Retirement Trigger | Retirement Verification | Owner | Target |
|----|-----------|----------------|--------------------|-------------------------|-------|--------|
| TEMP01 | [e.g., compatibility alias] | [reason] | [objective condition] | [verification command/test] | [owner] | [milestone/date] |

## Decision Log

| ADR | Decision | Status |
|-----|----------|--------|
| [NNNN](../adr/NNNN-title.md) | Brief description | Accepted |

## Open Questions

- [ ] [Unresolved questions that need answers before or during implementation]

## Acceptance Criteria

1. [Specific, verifiable criteria that the implementation must satisfy]
2. [These will be used by decompose-plan and execute-plan skills]
```

## ADR Template

```markdown
# NNNN: <Decision Title>

- Status: Proposed | Accepted | Rejected | Deprecated | Superseded by [NNNN](NNNN-title.md)
- Date: YYYY-MM-DD
- Deciders: [person/role, ...] <!-- optional -->
- Technical Story: [ticket/issue URL] <!-- optional -->

## Context and Problem Statement

[What problem are we solving now? Include concrete constraints, forces, and requirement links.]

## Decision Drivers

<!-- Include when trade-offs exist; remove if decision had no meaningful alternatives -->

- [driver 1]
- [driver 2]

## Considered Options

<!-- Include at least two options unless truly single-option; remove otherwise -->

- [option A]
- [option B]

## Decision Outcome

Chosen option: "[option X]", because:

- [reason 1 tied to driver/constraint]
- [reason 2 tied to driver/constraint]

## Consequences

### Positive

- [benefit]

### Negative

- [trade-off, risk, or cost]

### Neutral

- [other notable effects]

## Validation

- [How we verify success: metric/test/review checkpoint]

## Links

- Related ADR: [NNNN](NNNN-title.md) <!-- optional -->
- Supersedes: [NNNN](NNNN-title.md) <!-- optional -->
- Superseded by: [NNNN](NNNN-title.md) <!-- optional -->
- Related issue/PR/docs: [link] <!-- optional -->
```

## Sub Design Doc Template (for root-sub)

Use this template for each sub document listed in the root design doc's `Sub-Doc Index`.

```markdown
# <Topic> - <Subtopic> Sub-Design

## Sub-Doc Metadata

- Sub ID: SUB-X
- Root Design: `docs/plans/YYYY-MM-DD-<topic>-design.md`
- Owned Boundary: [Explicit component/domain ownership]

## Local Goals

- [Boundary-specific goals only]

## Local Non-Goals

- [Out-of-scope items for this boundary]

## Local Requirements

- REQ-SUB-X-01: [Implementable requirement]

## Local Design

[Boundary-specific design details. Keep root-level cross-domain policy out of this section.]

## Cross-Boundary Dependencies

- Depends on: [Other SUB IDs or Integration]
- Provides to: [Other SUB IDs or Integration]

## Local Acceptance Criteria

1. AC-SUB-X-01: [Verifiable criterion for this boundary]

## Decision Log

| ADR | Decision | Status |
|-----|----------|--------|
| [NNNN](../adr/NNNN-title.md) | Brief description | Accepted |
```
