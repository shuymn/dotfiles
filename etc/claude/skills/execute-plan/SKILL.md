---
name: execute-plan
description: Execute an approved implementation plan step by step with human review checkpoints. Use when you have a reviewed task plan and are ready to begin implementation.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, TodoWrite, Task]
---

# Plan Execution

Execute an approved implementation plan task by task, with human review checkpoints between batches. Follow each step exactly as written in the plan.

## When to Use

- You have an approved implementation plan (typically from the `decompose-tasks` skill)
- Input: a plan file in `docs/plans/`
- The user is ready to begin implementation

## Process

### Step 1: Load and Review Plan

1. Read the plan file specified by the user (or ask which one if not specified)
2. Review it critically before starting:
   - Are file paths still valid?
   - Has the codebase changed since the plan was written?
   - Are there any obvious gaps or concerns?
3. If concerns exist: **report them to the user before starting implementation**
4. Read the source design doc (linked in the plan header) to understand Acceptance Criteria
5. Register ALL tasks in TodoWrite as `pending`

### Step 2: Execute Batch

Execute tasks in batches of **3 tasks** (default). For each task:

1. **Mark** the task as `in_progress` in TodoWrite
2. **Follow each step exactly** as written in the plan:
   - Step 1: Write the failing test (copy the exact code from the plan)
   - Step 2: Run the test command and verify it fails with the expected error
   - Step 3: Write the minimal implementation (copy the exact code from the plan)
   - Step 4: Run the test command and verify it passes
   - Step 5: Execute the commit command from the plan
3. **Verify before moving on**: After each step, confirm the actual result matches the expected result in the plan
4. **Mark** the task as `completed` in TodoWrite

**If a step does not produce the expected result:**
- Do NOT proceed to the next step
- Do NOT improvise a fix
- See Stop Conditions below

### Step 3: Report and Checkpoint

After completing each batch:

1. Summarize what was implemented (list tasks completed)
2. Show verification output (test results, commands run, exit codes)
3. Display: **"Ready for feedback."**
4. **WAIT for the user to respond** — do NOT auto-proceed to the next batch

This checkpoint is mandatory. Skipping it or asking "shall I continue?" and proceeding without an answer violates this protocol.

### Step 4: Continue or Adjust

Based on user feedback:

- **No changes needed**: Proceed to the next batch
- **Adjustments needed**: Apply the requested changes, re-verify, then proceed
- **Plan needs revision**: Stop execution and suggest re-invoking `decompose-tasks`
- **Stop**: Halt execution entirely

### Step 5: Completion

After ALL tasks in the plan are completed:

1. **Run the full test suite** — not just individual test files
2. **Verify the build succeeds** (if applicable)
3. **Check each Acceptance Criterion** from the source design doc:
   - For each criterion, identify how to verify it
   - Run the verification
   - Report PASS or FAIL with evidence
4. Report the final status with all verification evidence

## Stop Conditions

**Stop executing immediately** and ask the user for guidance when:

- A test does not fail as expected in Step 2 (wrong error or passes unexpectedly)
- A test does not pass after implementing Step 3
- A commit fails (hook error, signing error, merge conflict)
- A dependency is missing that the plan did not account for
- The plan references a file or function that does not exist
- You discover the plan has a critical gap or contradiction
- Verification fails **3 or more times** for the same step

**When stopped:**
- Report exactly what happened (command, output, expected vs actual)
- Do NOT guess at a fix
- Do NOT modify the plan without user approval
- Wait for the user to decide how to proceed

## Verification Principle

Before claiming any task, batch, or the overall plan is complete:

1. **Identify** the verification command
2. **Run** it fresh — do not rely on cached results, previous runs, or assumptions
3. **Read** the full output, including exit codes and failure counts
4. **Confirm** the output supports the claim you are about to make
5. **Only then** make the claim, citing the evidence

**Prohibited language before verification evidence is shown:**
- "should work"
- "probably"
- "seems to"
- "I believe"
- "Great!"
- "Perfect!"
- "Done!"

These words signal that you are about to claim completion without evidence. Stop and verify first.

**This is non-negotiable.** If you catch yourself about to use these words, treat it as a red flag and run the verification command before saying anything.

## Adapting to Plan Deviations

Reality often diverges from plans. Here is how to handle common situations:

| Situation | Action |
|-----------|--------|
| Test command in plan is wrong (e.g., wrong path) | Fix the command, note the deviation, continue |
| Implementation needs a minor adjustment beyond plan | Make the minimal adjustment, note it in the batch report |
| Task is much more complex than planned | STOP. Report to user. May need plan revision. |
| A task depends on something the plan did not anticipate | STOP. Report the missing dependency. |
| Test passes without implementation (logic already exists) | STOP. The plan may be stale. Report to user. |
| User asks to skip a task | Skip it, mark as completed with note, continue |
