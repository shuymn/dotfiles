# DoD Recheck Mode

> All paths in this file (e.g., `scripts/`) are relative to the skill root directory, not to this file's location.

Independent verification of a completed task's DoD. This mode runs as a sub-agent (`fork_context=false`) in a separate session because the implementing agent cannot reliably catch its own blind spots — confirmation bias makes self-verification unreliable.

## Constraints

- The rechecking agent must NOT have implemented the task being rechecked — independence is what makes this verification meaningful.
- Do NOT modify any code, plan, or design artifacts. Editing during recheck would contaminate the verification evidence.
- Read-only + command execution only.

## Input

- Plan bundle path + task ID
- Recheck Input block (from implement mode's Step 3 output)

## Procedure

1. **Generate Header**: Run `scripts/digest-stamp.sh dod-recheck <plan-file>` to produce the recheck metadata header.
2. **Re-execute DoD Commands**: For each DoD command from the Recheck Input:
   - Run the command fresh.
   - Record: command, exit code, actual output, expected outcome, PASS/FAIL.
3. **Re-execute Quality Gate Commands**: If Quality Gates are listed in the Recheck Input:
   - Run each quality gate command.
   - Record: command, exit code, PASS/FAIL.
4. **Compute Overall Verdict**: `Overall Verdict: PASS` only when ALL DoD commands AND all Quality Gate commands PASS. Any failure → `Overall Verdict: FAIL`.
5. **Write Recheck Report**: Output to `...-task-<N>.dod-recheck.md` (where N is the task number).

## On FAIL

- Task completion is revoked — the task is not considered done.
- Progression to the next task is prohibited.
- Report the specific failing DoD items with evidence.

## Output Format

```markdown
# <Topic> - Task <N> DoD Recheck

## Recheck Metadata

<digest-stamp.sh output>
- **Overall Verdict**: PASS | FAIL

## DoD Verification

| # | Command | Exit Code | Expected | Actual | Verdict |
|---|---------|-----------|----------|--------|---------|
| 1 | [command] | [code] | [expected] | [actual] | PASS/FAIL |

## Quality Gate Verification

| # | Command | Exit Code | Verdict |
|---|---------|-----------|---------|
| 1 | [command] | [code] | PASS/FAIL |

## Decision

- Task <N> completion: confirmed/revoked
- Reason: [rationale]
```

## Task Completion Definition

A task is considered complete only when BOTH conditions are met:

1. **Implement mode**: All RED/GREEN/REFACTOR/DoD steps pass.
2. **DoD Recheck mode**: Independent sub-agent confirms all DoD items pass.

If `dod-recheck` returns FAIL, the implement completion is revoked and the task must be fixed before proceeding to the next task.
