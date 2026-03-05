---
name: adversarial-verify
description: "Adversarial verification of a completed task. Actively tries to break the implementation through edge cases, error paths, security probes, and concurrency attacks. Mandatory for Critical-tier tasks, optional for others. Runs as independent sub-agent. Use after execute-plan dod-recheck PASS."
allowed-tools: [Read, Bash, Grep, Glob, Write]
---

## Constraints

- The adversarial agent must NOT have implemented or DoD-rechecked the task — triple independence is required. Reason: the implementing and rechecking agents share context and assumptions; a third independent perspective is needed to find the blind spots that confirmation bias hides.
- Do NOT modify implementation code. Write only the adversarial report and attack test files. Reason: modifying code during adversarial verification would invalidate the DoD recheck evidence and conflate "finding vulnerabilities" with "fixing them."
- Attack test files must be clearly separated from production tests (use a dedicated directory or naming convention such as `*_adversarial_test.*`).

## Gate

Before starting adversarial verification, verify the dod-recheck gate:

1. Run `scripts/gate-check.sh <task-N.dod-recheck.md> <plan.md>`.
2. The dod-recheck file must exist, contain `Overall Verdict: PASS`, and the Source Digest must match the current plan file.
3. If the gate check fails, stop as `BLOCKED` and request the user to run `execute-plan dod-recheck` first.

## Input

- Plan bundle path + task ID
- Adversarial Verify Input block (from execute-plan implement mode's Step 3 output)
- Implementation files listed in the input block

For non-Critical tasks (optional invocation): the Adversarial Verify Input block is not auto-generated. The user must manually provide equivalent information (Task ID, Change Areas, Implementation Files, DoD Evidence).

## Procedure

1. **Generate Header**: Run `scripts/digest-stamp.sh adversarial-verify <plan-file>` to produce the verification metadata header.
2. **Load Context**: Read the Adversarial Verify Input block, all implementation files listed, and `references/attack-vectors.md`.
3. **Select Attack Categories**: Based on the Change Areas and Change Rationale, select applicable attack categories from the reference. Do NOT blindly apply all categories — choose only those relevant to the actual change.
4. **Execute Attacks**: For each selected attack vector:
   - Design a concrete test or probe targeting the implementation.
   - Create the test file (naming: `*_adversarial_test.*` or in a dedicated `adversarial/` directory).
   - Execute the test/probe.
   - Record: attack vector, test file, command, result (DEFENDED / VULNERABLE), evidence.
5. **Compute Verdict**: `Overall Verdict: PASS` only when ALL attack probes result in DEFENDED. Any VULNERABLE → `Overall Verdict: FAIL`.
6. **Write Report**: Output to `...-task-<N>.adversarial.md`.

## Edge Cases

- **Zero applicable attack categories**: If the Selection Guidance table yields no relevant categories for the change area, apply at minimum categories 1 (Input Boundary) and 2 (Error Handling) as a baseline. Record the rationale for limited applicability in the report.
- **Missing test infrastructure**: If the project lacks a test framework or runtime needed to execute attack probes, stop as `BLOCKED` and request the user to set up the necessary infrastructure. Do not skip attacks because tooling is absent.
- **Attack probe limit**: Target 3-8 attack probes per task. If the change area warrants more, cap at 15 and prioritize by risk severity. Document any pruning rationale.

## On FAIL

- Task completion is revoked — the task is not considered done.
- The full chain must be re-executed: `execute-plan(implement)` → `execute-plan(dod-recheck)` → `adversarial-verify`.
- Report specific vulnerabilities with reproduction steps.

## Output Format

```markdown
# <Topic> - Task <N> Adversarial Verification

## Verification Metadata

<digest-stamp.sh output>
- **Overall Verdict**: PASS | FAIL

## Attack Summary

| # | Category | Attack Vector | Test File | Result | Evidence |
|---|----------|--------------|-----------|--------|----------|
| 1 | [category] | [vector] | [file] | DEFENDED/VULNERABLE | [brief evidence] |

## Vulnerabilities Found

<!-- Only present when Overall Verdict is FAIL -->

| # | Attack Vector | Severity | Reproduction | Suggested Fix |
|---|--------------|----------|--------------|---------------|
| 1 | [vector] | [critical/high/medium] | [steps] | [suggestion] |

## Decision

- Task <N> adversarial verification: PASS/FAIL
- Reason: [rationale]
```

## Task Completion Definition (with Adversarial Verification)

For Critical-tier tasks, completion requires ALL three conditions:

1. **Implement mode**: All RED/GREEN/REFACTOR/DoD steps pass.
2. **DoD Recheck mode**: Independent sub-agent confirms all DoD items pass.
3. **Adversarial Verify**: Independent sub-agent confirms all attack probes are defended.

If `adversarial-verify` returns FAIL, the implement completion is revoked and the full chain must be re-executed.
