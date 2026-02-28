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

## Status

Proposed | Accepted | Deprecated | Superseded by [NNNN](link)

## Context

Why this decision is needed. What problem or requirement prompted it.

## Decision

What was decided. Be specific and unambiguous.

## Consequences

### Positive
- [Benefits of this decision]

### Negative
- [Trade-offs or costs of this decision]

### Neutral
- [Other effects worth noting]
```
