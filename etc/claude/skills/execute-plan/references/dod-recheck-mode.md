# DoD Recheck Mode

> `<skill-root>` means the directory containing the parent `SKILL.md`. Resolve `scripts/...` and `references/...` relative to `<skill-root>`, not to this file's location.

Independent verification of a completed task's DoD. This mode runs as a sub-agent (`fork_context=false`) in a separate session because the implementing agent cannot reliably catch its own blind spots — confirmation bias makes self-verification unreliable.

## Constraints

- The rechecking agent must NOT have implemented the task being rechecked — independence is what makes this verification meaningful.
- Do NOT modify any code, plan, or design artifacts. Editing during recheck would contaminate the verification evidence.
- Read-only + command execution only.

## Input

- Plan bundle path + task ID
- Recheck Input block (from implement mode's Step 3 output)

## Procedure

1. **Generate Header**: Run `<skill-root>/scripts/digest-stamp.sh dod-recheck <plan-file>` to produce the recheck metadata header.
2. **Re-execute DoD Commands**: For each DoD command from the Recheck Input:
   - Run the command fresh.
   - Record: command, exit code, actual output, expected outcome, PASS/FAIL.
3. **Re-execute Quality Gate Commands**: If Quality Gates are listed in the Recheck Input:
   - Run each quality gate command.
   - Record: command, exit code, PASS/FAIL.
3.5. **File Scope Verification**:
   - Run: `git diff --name-only <base>..HEAD | skit file-scope-check <plan-file> --task <N>`
   - The script reads the task's `Allowed Files` and `Exception Files` from the plan, matches changed files, and outputs a findings table.
   - If the script is unavailable, perform the check manually:
     - Read the task's `Allowed Files` glob patterns from the plan.
     - Read the task's `Exception Files` patterns from the plan (if defined).
     - Compare implementation files against `Allowed Files` first, then `Exception Files`.
     - Files matching `Exception Files` but not `Allowed Files`: status `OK (exception)`.
     - Files matching neither: status `SCOPE_DEVIATION`.
   - Record in `## File Scope Findings` table:

     | # | File | Matched Pattern | Status |
     |---|------|----------------|--------|
     | 1 | [path] | [pattern or EXCEPTION(pattern) or NONE] | OK / OK (exception) / SCOPE_DEVIATION |

   - **Scope deviation policy**: Any `SCOPE_DEVIATION` forces `Overall Verdict: FAIL`, regardless of risk tier.
   - If Heightened Scrutiny is also performed, include scope deviation findings in that section as well.

4. **Compute Overall Verdict**:
   - Base condition: `Overall Verdict: PASS` only when ALL DoD commands AND all Quality Gate commands PASS.
   - Scope deviation override: if any `SCOPE_DEVIATION` exists, set `Overall Verdict: FAIL`.
   - Heightened scrutiny override: if any finding has severity `critical` or `high`, set `Overall Verdict: FAIL` even when DoD/Quality Gate commands pass.
5. **Write Recheck Report**: Output to `...-task-<N>.dod-recheck.md` (where N is the task number).
6. Write file paths in repository-relative form. If you mention a skill helper command, render it as `scripts/<name>.sh`, never an absolute filesystem path.

## Heightened Scrutiny (Sensitive/Critical)

When the Recheck Input indicates Risk Tier is Sensitive or Critical, perform additional inspection beyond DoD command re-execution:

1. Read the implementation diff for files changed by the task.
2. Inspect for:
   - Unvalidated inputs at trust boundaries
   - Missing error handling on failure paths
   - Hardcoded values (secrets, credentials, magic numbers)
   - Silent failures (swallowed exceptions, ignored error returns)
   - Unsafe type coercions or unchecked casts
3. Record findings in `## Heightened Scrutiny Findings` table:

| # | File | Line(s) | Category | Finding | Severity |
|---|------|---------|----------|---------|----------|
| 1 | [path] | [lines] | [category] | [description] | critical/high/warning |

- Severity policy:
  - `critical`: directly exploitable by an attacker (e.g., unauthenticated path, credentials exposure). Forces `Overall Verdict: FAIL`.
  - `high`: high likelihood of causing production outage or state corruption (e.g., swallowed errors leading to inconsistent state). Forces `Overall Verdict: FAIL`.
  - `warning`: best-practice violation with limited immediate impact. Advisory only.
- Allowed severity values are exactly: `critical`, `high`, `warning`.
- For Critical-tier tasks, note that `adversarial-verify` is required separately after dod-recheck PASS.

## Standard Inspection (Standard with Implementation Files)

When the Recheck Input indicates Risk Tier is Standard and the task's Files block contains Create/Modify entries for implementation files, perform a standard code inspection.

**Implementation file definition**: Files in the Create/Modify entries whose paths do NOT match any of: `*test*`, `*spec*`, `*.md`, `docs/*`, `*.txt`.

**Inspection items** (subset of Heightened Scrutiny):
- Hardcoded values (secrets, credentials, magic numbers)
- Silent failures (swallowed exceptions, ignored error return values)

Record findings in `## Standard Inspection Findings` table:

| # | File | Line(s) | Category | Finding | Severity |
|---|------|---------|----------|---------|----------|
| 1 | [path] | [lines] | [category] | [description] | warning |

- All findings are severity `warning` (advisory only, no FAIL override).
- This inspection does NOT apply when Risk Tier is Sensitive or Critical (Heightened Scrutiny covers those).

## On FAIL

- Task completion is revoked — the task is not considered done.
- Progression to the next task is prohibited.
- Report the specific failing DoD/Quality Gate items and any `critical`/`high` heightened scrutiny findings with evidence.

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

## File Scope Findings

<!-- Present when Allowed Files are defined for the task -->

| # | File | Matched Pattern | Status |
|---|------|----------------|--------|
| 1 | [path] | [pattern or EXCEPTION(pattern) or NONE] | OK / OK (exception) / SCOPE_DEVIATION |

## Heightened Scrutiny Findings

<!-- Present when Risk Tier is Sensitive or Critical -->

| # | File | Line(s) | Category | Finding | Severity |
|---|------|---------|----------|---------|----------|
| 1 | [path] | [lines] | [category] | [description] | critical/high/warning |

## Standard Inspection Findings

<!-- Present when Risk Tier is Standard and Files contain implementation files -->

| # | File | Line(s) | Category | Finding | Severity |
|---|------|---------|----------|---------|----------|
| 1 | [path] | [lines] | [category] | [description] | warning |

## Decision

- Task <N> completion: confirmed/revoked
- Reason: [rationale]
```

## Task Completion Definition

A task is considered complete only when BOTH conditions are met:

1. **Implement mode**: All RED/GREEN/REFACTOR/DoD steps pass.
2. **DoD Recheck mode**: Independent sub-agent confirms all DoD items pass.

If `dod-recheck` returns FAIL, the implement completion is revoked and the task must be fixed before proceeding to the next task.
