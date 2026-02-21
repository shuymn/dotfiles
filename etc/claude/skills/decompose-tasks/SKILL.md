---
name: decompose-tasks
description: Decompose a design document into a granular implementation plan with TDD steps. Use when you have an approved design doc and need to create a step-by-step task breakdown before implementation.
allowed-tools: [Read, Write, Edit, Grep, Glob, TodoWrite, Bash]
---

# Task Decomposition from Design Doc

Convert an approved design document into a granular, step-by-step implementation plan where each task follows a TDD cycle and represents a single, independently testable unit of work.

## When to Use

- You have an approved design doc and need an implementation plan
- Input: a design doc in `docs/plans/` (typically created by the `design-doc` skill)
- Output: `docs/plans/YYYY-MM-DD-<topic>-plan.md`

## <HARD-GATE>

Do NOT begin any implementation until the plan is explicitly approved by the user.

No exceptions. Not even "just to test one thing" or "the first task is trivial."

## Granularity Rules

Each task must satisfy ALL of these criteria:

- **Single purpose** — one verifiable outcome. If the task name contains "and", split it into separate tasks
- **Independently testable** — the task produces a result that can be verified on its own
- **Complete TDD cycle** — every task includes RED → GREEN → REFACTOR steps
- **Atomic commit** — each task ends with a commit

**Time guideline:** Most tasks should take 2-5 minutes. This is a guideline, not a hard constraint. The criteria above are the real measure of correct granularity.

If a task meets all four criteria above but exceeds 5 minutes, **keep it as-is**. Add a note in the plan:

> This task exceeds the 2-5 min guideline because: [reason]

**Do NOT force a split when:**
- The split would create an untestable intermediate state
- The split requires artificial scaffolding that will be immediately removed
- The components are so tightly coupled that testing them separately would require extensive mocking
- The task is inherently atomic (e.g., a database migration, a complex algorithm with no meaningful partial state)

**Self-check:** Read each task description aloud. If you need to take a breath in the middle, it is probably too big — but verify against the four criteria before splitting.

## Plan Structure

### Header (Required)

Every plan starts with this header:

```markdown
# [Feature] Implementation Plan

**Source**: `docs/plans/YYYY-MM-DD-<topic>-design.md`
**Goal**: [One sentence describing the end result]
**Architecture**: [2-3 sentences on the high-level approach]
**Tech Stack**: [Key technologies, frameworks, libraries]
```

### Task Format

Each task follows this exact structure:

```markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/from/project-root/to/file.ext`
- Modify: `exact/path/from/project-root/to/existing.ext` (what changes and why)

**Step 1: Write failing test**

\`\`\`<language>
// Complete test code — not a description, not a placeholder
\`\`\`

**Step 2: Run test to verify it fails**

Run: `<exact test command with flags>`
Expected: FAIL with `<expected error message or pattern>`

**Step 3: Write minimal implementation**

\`\`\`<language>
// Complete implementation code — minimal to pass the test
\`\`\`

**Step 4: Run test to verify it passes**

Run: `<exact test command with flags>`
Expected: PASS (all tests green)

**Step 5: Commit**

\`\`\`bash
git add <specific-files>
git commit -m "<type>(<scope>): <description>"
\`\`\`
```

**Requirements for task content:**

| Element | Required | Bad Example | Good Example |
|---------|----------|-------------|--------------|
| File paths | Exact, from project root | `file.py` | `src/auth/validator.py` |
| Test code | Complete, runnable | "Add test for validation" | Full test function with assertions |
| Implementation code | Complete, minimal | "Implement the validator" | Full function body |
| Test commands | Exact, with flags | "Run the tests" | `pytest tests/auth/test_validator.py::test_email_format -v` |
| Expected output | Specific pattern | "Should fail" | `FAIL with "AssertionError: expected validate_email to be defined"` |
| Commit message | Conventional format | "Add stuff" | `feat(auth): add email format validation` |

### Task Ordering Strategy

Order tasks to build incrementally, with each task building on the previous:

1. **Setup tasks** — project initialization, tooling, configuration
2. **Foundation tasks** — core data structures, storage, base utilities
3. **Component tasks** — individual components (one task per component)
4. **Integration tasks** — wiring components together
5. **Feature tasks** — user-facing functionality, interactions
6. **Polish tasks** — styling, UX improvements, edge cases
7. **Testing tasks** — E2E tests, integration tests beyond unit level

## Process

### Step 1: Load Design Doc

1. Read the design doc specified by the user (or ask which one to use if not specified)
2. Read the Acceptance Criteria section carefully — these drive the task list
3. Read all related ADRs to understand design decisions and constraints
4. Identify the tech stack and testing framework

### Step 2: Analyze and Decompose

1. List all features and components from the design
2. Build a dependency graph: which components depend on which
3. Order components by dependency (foundations first)
4. For each component:
   - Identify the test file path and implementation file path
   - Determine what constitutes a failing test (what does not exist yet)
   - Determine the minimal implementation to pass that test
   - Determine the commit scope

### Step 3: Write Plan

1. Create the plan file: `docs/plans/YYYY-MM-DD-<topic>-plan.md`
   - Use the same date prefix as the source design doc
   - Create the directory if it does not exist: `mkdir -p docs/plans`
2. Write the header with Source, Goal, Architecture, Tech Stack
3. Write each task following the exact Task Format above
4. Verify every task has:
   - Exact file paths (from project root)
   - Complete code (not descriptions or placeholders)
   - Exact commands with expected output
   - A commit step with a proper message

### Step 4: Review with User

1. Present the plan to the user
2. Request review using AskUserQuestionTool
3. Apply feedback and update the plan
4. Repeat until the user explicitly approves
5. After approval, suggest using the `execute-plan` skill

## Key Principles

- **DRY**: Do not repeat yourself across tasks
- **YAGNI**: Only plan what the design doc specifies — do not add features
- **TDD**: Every task starts with a failing test. No exceptions. No rationalizations.
  - "Too simple to test" → Simple code breaks. The test takes 30 seconds to write.
  - "I will test it after" → Tests written after pass immediately and prove nothing.
  - "Just as a reference" → You will adapt it. That is testing after. Start from the test.
- **Frequent Commits**: One commit per task, always
- **Exact over vague**: A plan that cannot be followed by someone with zero codebase context is not specific enough
