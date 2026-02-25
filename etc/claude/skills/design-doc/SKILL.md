---
name: design-doc
description: Creates or updates a design document through iterative dialogue with the user, including a mandatory clarification gate before drafting. Use when starting a new feature, system design, or architectural change that needs a written design before implementation. Produces design docs and ADRs.
allowed-tools: [Read, Write, Edit, Grep, Glob, TodoWrite, Bash]
---

# Design Doc Creation

Create design documents through iterative dialogue with the user, capturing design decisions as Architecture Decision Records (ADRs).

## When to Use

- Starting a new feature, system design, or architectural change
- Need a written design before implementation
- Want to capture design decisions as ADRs

## <HARD-GATE>

Do NOT take any of these actions until the design doc is explicitly approved by the user:

- Write any implementation code or scaffolding
- Invoke the `decompose-tasks` skill
- Create an implementation plan
- Create any project files outside of `docs/`

No exceptions. Not even "just setting up the structure" or "a quick prototype to validate."

## Process

### Phase 1: Context Exploration

Before writing anything, understand the landscape:

1. Explore the project structure, existing code, and related documentation
2. Check for existing design docs in `docs/plans/`
3. Check for existing ADRs in `docs/adr/` — **use a tiered reading strategy:**
   - **Always:** List filenames only first (`ls docs/adr/`) to get an overview
   - **Then:** Read only ADRs that are clearly relevant to the current design topic (judge by title)
   - **Never:** Read all ADRs upfront — in large projects this will consume context for no benefit
   - If unsure whether an ADR is relevant, read just its Title and Status lines before committing to the full content
4. Identify related components, APIs, or systems that the design will interact with
5. Create a TodoWrite checklist to track the design process phases

### Phase 1.5: Clarification Gate (Required)

Before drafting the design, remove requirement ambiguity explicitly.

1. Build a clarification list from user requests, existing docs, and code context.
2. Resolve each item with the user one-by-one:
   - Use AskUserQuestionTool.
   - Ask **one question at a time** (do not batch multiple questions).
   - Prefer multiple-choice options when feasible.
3. Classify each clarification item as one of:
   - `resolved` (explicit answer exists)
   - `assumed` (no answer yet, but safe temporary assumption documented)
   - `blocked` (cannot continue without answer)
4. Do not start design drafting while any `blocked` item remains.
5. Record outcomes in the design doc under `## Clarifications` with:
   - Question
   - Answer or assumption
   - Impact on scope/design
   - Status (`resolved` or `assumed`)

### Phase 2: Initial Design Draft

1. Create the initial design doc draft
2. Write to: `docs/plans/YYYY-MM-DD-<topic>-design.md`
   - Create the directory if it does not exist: `mkdir -p docs/plans`
3. Present the draft to the user and request feedback

### Phase 3: Feedback Loop (Core Loop)

Repeat until the user explicitly approves the design:

1. User provides feedback
2. Update the design doc to address the feedback
3. If a design decision was made during this iteration:
   - Create or update an ADR (see Phase 4)
   - Add a link to the ADR in the design doc's Decision Log section
4. Present the updated design doc and request review

**Key behaviors in this loop:**
- Do not assume approval from vague responses. Ask explicitly: "Is this design approved?"
- If the user raises a concern, address it before moving on
- If multiple alternatives are discussed, capture the chosen one in an ADR

### Phase 4: ADR Management

When a significant design decision is made, record it as an ADR.

**Output path:** `docs/adr/NNNN-<title>.md`

**Numbering:**
- Check existing ADRs: `ls docs/adr/ 2>/dev/null | sort -n | tail -1`
- Use the next sequential number (zero-padded to 4 digits)
- If no ADRs exist, start with `0001`
- Create the directory if missing: `mkdir -p docs/adr`

**ADR format:**

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

**When to create an ADR:**
- Technology or library selection
- Architectural pattern choice (e.g., monolith vs microservices)
- API design decisions
- Data model decisions
- Trade-offs between competing requirements
- Deviations from established project conventions

**When NOT to create an ADR:**
- Trivial implementation details
- Decisions that are obvious given the project context
- Formatting or style choices already covered by project conventions

### Phase 5: Finalization

1. Save the final version of the design doc
2. Verify all design decisions have corresponding ADRs
3. Verify the Decision Log section in the design doc links to all related ADRs
4. Suggest the `decompose-tasks` skill as the next step

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

## Decision Log

| ADR | Decision | Status |
|-----|----------|--------|
| [NNNN](../adr/NNNN-title.md) | Brief description | Accepted |

## Open Questions

- [ ] [Unresolved questions that need answers before or during implementation]

## Acceptance Criteria

1. [Specific, verifiable criteria that the implementation must satisfy]
2. [These will be used by decompose-tasks and execute-plan skills]
```
