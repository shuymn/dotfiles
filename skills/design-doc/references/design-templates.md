# Design Doc Templates

## Design Doc Template

Use this structure as a starting point. Default to the Core Profile sections. Add default-prohibited sections only when their trigger conditions are met (see SKILL.md § Scale-Appropriate Depth).

```markdown
# <Topic> - Design

## Overview

[1-2 paragraphs summarizing what this design covers and why]

## Goals

- [What this design aims to achieve]

## Non-Goals

<!-- List only things a reader might assume are in scope from Goals, but are excluded. Omit anything with no logical connection to the goals. -->
- [Item a reader could infer is in scope from Goals, but is explicitly excluded]

## Background (Optional)

[Use when extra context is needed beyond Overview (prior art, related systems, constraints).]

## Clarifications

| Question | Answer / Assumption | Impact | Status |
|----------|----------------------|--------|--------|
| [What needed clarification] | [Final answer or explicit assumption] | [How design/scope changes] | resolved / assumed |

## Existing Codebase Constraints (Required for non-greenfield)

| Constraint ID | Source (file/test) | Constraint | Impact on Design | Required Verification |
|---------------|--------------------|------------|------------------|-----------------------|
| CONS-01 | [path/to/file or test] | [Existing assumption or coupling] | [How this limits or shapes design] | [How regression/contract will be checked] |

## Risk Classification

| Area | Risk Tier | Change Rationale |
|------|-----------|-----------------|
| [e.g., Auth token validation] | Critical | Defect Impact: [what breaks on defect] / Blast Radius: [scope of impact] |
| [e.g., API response schema] | Sensitive | Defect Impact: [what breaks on defect] / Blast Radius: [scope of impact] |
| [e.g., Dashboard component] | Standard | Not Critical: [reason] / Not Sensitive: [reason] |

<!-- Required when design is non-greenfield, or when greenfield touches Critical domains (auth, billing, access control, encryption, PII). -->
<!-- Critical/Sensitive require structured Change Rationale: "Defect Impact: [...] / Blast Radius: [...]". Standard requires semantic justification: "Not Critical: [reason] / Not Sensitive: [reason]". If justification cannot be written, escalate to Sensitive or higher (confidence gate). -->
<!-- Tier semantics: Critical = irreversible damage, security breach, data loss, financial harm, compliance violation. Sensitive = silent state corruption, contractual interface breakage, coordinated rollback required. Standard = visible, locally-contained failure with straightforward rollback. Exact areas depend on product/domain context. -->

## Decomposition Strategy

- Split Decision: single | root-sub
- Decision Basis: [Which Boundary Inventory signals and contract conditions triggered this decision]
- Root Scope: [Global responsibilities and integration-only responsibilities]

### Boundary Inventory

| Boundary | Owns Requirements/AC | Primary Verification Surface | TEMP Lifecycle Group | Parallel Stream | Depends On |
|----------|----------------------|------------------------------|----------------------|-----------------|------------|
| [Boundary name] | [REQ/AC IDs or summary, or `Integration-only`] | [primary test or verification surface] | [shared TEMP group or `none`] | yes | [Boundary names or `none`] |

<!-- Required for both `single` and `root-sub`. -->
<!-- Use `Integration-only` for root-only integration rows. -->
<!-- `Parallel Stream` must be `yes` or `no`. -->
<!-- `Depends On` is a comma-separated list of Boundary names or `none`. -->

### Sub-Doc Index (required when root-sub)

| Sub ID | File | Owned Boundary | Owns Requirements/AC |
|--------|------|----------------|----------------------|
| SUB-A | docs/plans/<topic>/sub-a-design.md | [boundary] | [ID ranges or summary] |

### Root Coverage (required when root-sub)

| Root Requirement/AC | Covered By (Sub ID or Integration) | Notes |
|---------------------|------------------------------------|-------|
| [ROOT-REQ/ROOT-AC] | [SUB-A / Integration] | [mapping rationale] |

## Proposed Solution

[What we are changing and why this approach is chosen.]

## Detailed Design

[Use diagrams (Mermaid preferred over ASCII art) where they add clarity.]

## Alternatives Considered (Optional)

[Use when there are meaningful trade-offs or rejected options.]

## Risks & Mitigations (Optional)

[Use when failure modes, rollout risks, or uncertainty are non-trivial.]

## Verification Plan (Optional)

[How success is validated: tests, benchmarks, measurable checks.]
[This describes verification methods/evidence, not the acceptance bar itself.]

## Operational Considerations (Optional)

[Use only when production operations are materially impacted (rollout, monitoring, dependency coordination).]

## Compatibility & Sunset

[Required for breaking changes or staged migrations.]

### Temporary Mechanism Index

Use stable IDs (`TEMPxx`). For each entry, point to the lifecycle record (`ADR` preferred; local ledger acceptable for small/local mechanics).

| ID | Mechanism | Lifecycle Record | Status |
|----|-----------|------------------|--------|
| TEMP01 | [e.g., compatibility alias] | [temp-compat-alias](/docs/adr/<topic>/temp-compat-alias.md) or local | active |

### Sunset Closure Checklist

Required for every `TEMPxx`, even when details are captured in ADR.

| ID | Introduced For | Retirement Trigger | Retirement Verification | Removal Scope |
|----|----------------|--------------------|-------------------------|---------------|
| TEMP01 | [reason] | [objective condition] | [verification command/test] | [what is deleted/disabled] |

If coordination or handoff risk exists, add optional `Owner` and `Target` columns.

## Decision Log

| ADR | Decision | Status |
|-----|----------|--------|
| [adopt-grpc-for-public-api](/docs/adr/<topic>/adopt-grpc-for-public-api.md) | Brief description | Accepted |

## Open Questions

- [ ] [Unresolved questions that need answers before or during implementation]

## Acceptance Criteria

| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
|-------|-----------|---------------|---------------------|---------------------|----------------------|
| AC01 | [Ubiquitous/Event-Driven/Unwanted/State-Driven/Optional] | [behavioral/schema/api-contract/cli-contract/none] | [EARS-formatted requirement sentence] | [EARS rationale: why this type was chosen] [Concrete verification method with expected outcome] | `<exact command>` or `TBD-at-plan` |

<!-- See ears-types.md for EARS type definitions, syntax templates, and selection guidance. -->
<!-- Contract Type: schema (data shape validation), api-contract (API interface compliance), cli-contract (CLI behavior compliance), behavioral (logic/state behavior), none (no specific contract). Default: behavioral. -->
<!-- For replacement/removal/fail-closed intent, include both prohibited-path and allowed-path rows. -->
<!-- Keep this as the pass/fail bar; reference Verification Plan only as supporting evidence. -->
<!-- Verification Command: exact executable command that produces deterministic PASS/FAIL. Use TBD-at-plan when the command is unknown at design time; decompose-plan must resolve it. -->
```

## ADR Template

```markdown
# <Decision Title>

- Status: Proposed | Accepted | Rejected | Deprecated | Superseded by [<subject>](<subject>.md)
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

## Sunset Clause (Only for TEMPxx decisions)

- TEMP ID: TEMPxx
- Introduced For: [why this is temporary]
- Retirement Trigger: [objective condition]
- Retirement Verification: [how closure is proven]
- Removal Scope: [what is removed/disabled]
- Owner/Target: [optional; include when coordination or handoff risk exists]

## Validation

- [How we verify success: metric/test/review checkpoint]

## Links

- Related ADR: [<subject>](<subject>.md) <!-- optional -->
- Supersedes: [<subject>](<subject>.md) <!-- optional -->
- Superseded by: [<subject>](<subject>.md) <!-- optional -->
- Related issue/PR/docs: [link] <!-- optional -->
```

## Sub Design Doc Template (for root-sub)

Use this template for each sub document listed in the root design doc's `Sub-Doc Index`.

```markdown
# <Topic> - <Subtopic> Sub-Design

## Sub-Doc Metadata

- Sub ID: SUB-X
- Root Design: `docs/plans/<topic>/design.md`
- Owned Boundary: [Explicit component/domain ownership; must exactly match the root `Boundary Inventory` `Boundary` value]

## Local Goals

- [Boundary-specific goals only]

## Local Non-Goals

<!-- List only things a reader might assume are in this boundary's scope from Local Goals, but are excluded. -->
- [Item a reader could infer is in this boundary's scope, but is explicitly excluded]

## Local Requirements

- REQ-SUB-X-01: [Implementable requirement]

## Local Design

[Boundary-specific design details. Keep root-level cross-domain policy out of this section.]

## Cross-Boundary Dependencies

- Depends on: [Other SUB IDs or Integration]
- Provides to: [Other SUB IDs or Integration]

## Local Acceptance Criteria

| AC ID | EARS Type | Contract Type | Requirement Sentence | Verification Intent | Verification Command |
|-------|-----------|---------------|---------------------|---------------------|----------------------|
| AC-SUB-X-01 | [Ubiquitous/Event-Driven/Unwanted/State-Driven/Optional] | [behavioral/schema/api-contract/cli-contract/none] | [EARS-formatted requirement sentence] | [EARS rationale] [Verification method] | `<exact command>` or `TBD-at-plan` |

## Decision Log

| ADR | Decision | Status |
|-----|----------|--------|
| [adopt-grpc-for-public-api](/docs/adr/<topic>/adopt-grpc-for-public-api.md) | Brief description | Accepted |
```
