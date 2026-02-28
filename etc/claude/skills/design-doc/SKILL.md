---
name: design-doc
description: Creates or updates a design document through iterative dialogue, producing design docs and ADRs. Use when planning a new feature, API design, system architecture, data model change, or any non-trivial change that benefits from written design before implementation.
allowed-tools: [Read, Write, Edit, Grep, Glob, TodoWrite, Bash]
---

# Design Doc Creation

Create design documents through iterative dialogue with the user, capturing design decisions as Architecture Decision Records (ADRs).

## <HARD-GATE>

Do NOT take any of these actions until the design doc is explicitly approved by the user:

- Write any implementation code or scaffolding
- Invoke the `decompose-plan` skill
- Create an implementation plan
- Create any project files outside of `docs/`

No exceptions. Not even "just setting up the structure" or "a quick prototype to validate."

## Lifecycle Contract for Breaking Changes

For breaking changes or staged migrations, the design doc must specify lifecycle closure, not only end-state architecture.

- Add a `## Compatibility & Sunset` section.
- Add a `Temporary Mechanism Ledger` table with stable IDs (`TEMPxx`).
- Every `TEMPxx` must define:
  - Mechanism
  - Introduced for (why it exists)
  - Retirement trigger (objective condition)
  - Retirement verification (how closure is proven)
  - Owner and target milestone/date
- Missing retirement definitions are design gaps, not implementation details.

## Decomposition Strategy Contract (Single vs Root/Sub)

Default to a single design doc. Use root/sub split only when structural conditions require it.

- Default: `Split Decision: single`
- Do not split only because the document is long.
- Record the decision in the design doc under `## Decomposition Strategy`.

Split is required if any of these are true:

- Distinct domains/components have independent acceptance flows and verification commands.
- Staged migration or `TEMPxx` lifecycle differs by domain.
- Work is expected to proceed in parallel streams with clear ownership boundaries.
- A single doc cannot keep `requirements -> tasks` traceability unambiguous.

Split is discouraged (keep single) if any of these are true:

- Most requirements target one cohesive component boundary.
- Verification is primarily a single integrated flow.
- Proposed sub-doc boundaries would create many cross-boundary tasks.

If `Split Decision: root-sub`, require:

- Root doc with global scope, shared constraints, cross-domain dependencies, and integration acceptance criteria.
- One sub design doc per boundary with local requirements and acceptance criteria.
- Explicit boundary ownership (what each sub owns, and what remains integration-only).
- Root-level coverage table mapping root requirements/acceptance criteria to sub-doc owners or integration tasks.

## Process

### Phase 1: Context Exploration

Before writing anything, understand the landscape:

1. Explore the project structure, existing code, and related documentation
2. Check for existing design docs in `docs/plans/`
3. Check for existing ADRs in `docs/adr/` — **use a tiered reading strategy:**
   - **Always:** List filenames only first (`rtk ls docs/adr/`) to get an overview
   - **Then:** Read only ADRs that are clearly relevant to the current design topic (judge by title)
   - **Never:** Read all ADRs upfront — in large projects this will consume context for no benefit
   - If unsure whether an ADR is relevant, read just its Title and Status lines before committing to the full content
4. Identify related components, APIs, or systems that the design will interact with
5. Create a TodoWrite checklist to track the design process phases
6. Determine whether the request includes a breaking change or staged migration; if yes, enumerate candidate temporary mechanisms to track as `TEMPxx`.
7. Determine decomposition strategy (`single` or `root-sub`) using the Decomposition Strategy Contract.

### Phase 1.5: Clarification Gate (Required)

Before drafting the design, remove requirement ambiguity explicitly.

1. Build a clarification list from user requests, existing docs, and code context.
2. Resolve each item with the user one-by-one:
   - Use AskUserQuestionTool.
   - Include in the question text: (1) what decision this resolves, (2) which section of the design doc or artifact the answer will affect.
   - Ask **one question at a time** (do not batch multiple questions).
   - Prefer multiple-choice options when feasible.
3. Classify each clarification item as one of:
   - `resolved` (explicit answer exists)
   - `assumed` (no answer yet, but safe temporary assumption documented; requires finalization trigger)
   - `blocked` (cannot continue without answer)
4. Do not start design drafting while any `blocked` item remains.
5. For breaking-change designs, treat missing retirement trigger/verification for any `TEMPxx` as `blocked`.
6. Record outcomes in the design doc under `## Clarifications` with:
   - Question
   - Answer or assumption
   - Finalization trigger (for `assumed`: what condition or event will convert this to `resolved`)
   - Impact on scope/design
   - Status (`resolved` or `assumed`)

### Phase 2: Initial Design Draft

1. Create the initial design doc draft
2. Write to: `docs/plans/YYYY-MM-DD-<topic>-design.md`
   - Create the directory if it does not exist: `mkdir -p docs/plans`
3. If `Split Decision: root-sub`, also create sub docs at:
   - `docs/plans/YYYY-MM-DD-<topic>-<subtopic>-design.md`
   - Use the sub-doc template: [design-templates.md](references/design-templates.md#sub-design-doc-template-for-root-sub)
4. Present the draft to the user and request feedback

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
- Use a concise, verb-led kebab-case title (example: `0042-adopt-grpc-for-public-api.md`)

**ADR format:** See [design-templates.md](references/design-templates.md#adr-template).

**ADR quality bar (derived from proven ADR templates/examples):**
- One ADR must capture exactly one decision.
- Include top metadata: `Status`, `Date`, and `Deciders` (if known).
- Write `Context and Problem Statement` with concrete forces, constraints, and requirement links.
- If trade-offs exist, include `Decision Drivers` and `Considered Options` (at least two unless truly single-option).
- Use `Decision Outcome` to name the chosen option and explain why it wins.
- In `Consequences`, capture positive/negative/neutral impacts plus concrete follow-up work.
- Add `Validation` to describe how success is measured (metric/test/review checkpoint).
- Add `Links` to related ADRs, tickets, PRs, and docs.

**ADR lifecycle rules:**
- Treat ADRs as immutable history: do not rewrite accepted decisions to fit new reality.
- When a decision changes, create a new ADR and connect it using `Supersedes` / `Superseded by`.
- Keep status transitions explicit (`Proposed` -> `Accepted` -> `Deprecated`/`Superseded`/`Rejected`).

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
4. For breaking-change designs, verify all `TEMPxx` entries include retirement trigger and retirement verification.
5. Verify `## Decomposition Strategy` is complete and consistent with produced design files:
   - Every `Sub-Doc Index` file path exists.
   - Every `Root Coverage` entry references a valid sub ID or `Integration`.
   - Every sub ID referenced in `Root Coverage` exists in `Sub-Doc Index`.
   - Boundary ownership text is explicit and non-overlapping.
6. Verify each ADR meets the quality bar (metadata, context/problem, decision outcome, consequences, links).
7. Verify supersession links are coherent (`Supersedes`/`Superseded by` are reciprocal where applicable).
8. Suggest the `decompose-plan` skill as the next step

## Design Doc Template

See [design-templates.md](references/design-templates.md#design-doc-template) for the full template. Adapt sections as needed — not every section is required for every design.
