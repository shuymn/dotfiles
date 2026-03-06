---
name: adversarial-verify
description: "Adversarial verification of a completed task — tries to break the implementation through edge cases, error paths, security probes, and concurrency attacks. Required for Critical/Sensitive tiers (conditionally for Standard with impl files). Use after execute-plan dod-recheck PASS."
allowed-tools: [Read, Bash, Grep, Glob, Write]
---

## Path Resolution

- `<skill-root>` means the directory containing this `SKILL.md`.
- Resolve `scripts/...` and `references/...` relative to `<skill-root>`, not the caller's current working directory.
- When executing local helpers, use explicit paths such as `<skill-root>/scripts/...`.

## Constraints

- The adversarial agent must NOT have implemented or DoD-rechecked the task — triple independence is required. Reason: the implementing and rechecking agents share context and assumptions; a third independent perspective is needed to find the blind spots that confirmation bias hides.
- Do NOT modify implementation code. Write only the adversarial report and attack test files. Reason: modifying code during adversarial verification would invalidate the DoD recheck evidence and conflate "finding vulnerabilities" with "fixing them."
- Attack test files must be clearly separated from production tests (use a dedicated directory or naming convention such as `*_adversarial_test.*`).

## Gate

Before starting adversarial verification, verify the dod-recheck gate:

1. Run `<skill-root>/scripts/gate-check.sh <task-N.dod-recheck.md> <plan.md>`.
2. The dod-recheck file must exist, contain `Overall Verdict: PASS`, and the Source Digest must match the current plan file.
3. If the gate check fails, stop as `BLOCKED` and request the user to run `execute-plan dod-recheck` first.

## Tier-Based Invocation Policy

| Risk Tier | Invocation | Minimum Probes | Attack Scope |
|-----------|------------|----------------|--------------|
| Critical | Mandatory | 3 | All applicable categories |
| Sensitive | Mandatory | 2 | Category 1 (Input Boundary) + most relevant 1 additional category |
| Standard (impl) | Conditional Mandatory | 1 | Most relevant 1 category |
| Standard (non-impl) | Optional | — | User-selected |

**Implementation file definition**: Same as `dod-recheck-mode.md` Standard Inspection — Files in Create/Modify entries whose paths do NOT match any of: `*test*`, `*spec*`, `*.md`, `docs/*`, `*.txt`. Standard (impl) applies when the task's Files block contains at least one implementation file.

## Input

- Plan bundle path + task ID
- Adversarial Verify Input block (from execute-plan implement mode's Step 3 output)
- Implementation files listed in the input block

For Standard (non-impl) tasks (optional invocation), the Adversarial Verify Input block is not auto-generated. The user must manually provide equivalent information (Task ID, Change Areas, Implementation Files, DoD Evidence).

## Procedure

1. **Generate Header**: Run `<skill-root>/scripts/digest-stamp.sh adversarial-verify <plan-file>` to produce the verification metadata header.
2. **Load Context**: Read the Adversarial Verify Input block, all implementation files listed, and `references/attack-vectors.md` (including the `## Project-Specific Vectors` section).
3. **Select Attack Categories**: Based on the Change Areas and Change Rationale, select applicable attack categories from the reference. Do NOT blindly apply all categories — choose only those relevant to the actual change. If `## Project-Specific Vectors` contains vectors matching the change characteristics, include them as additional probe targets regardless of the selected categories.
4. **Execute Attacks**: For each selected attack vector:
   - Design a concrete test or probe targeting the implementation.
   - Create the test file (naming: `*_adversarial_test.*` or in a dedicated `adversarial/` directory).
   - Execute the test/probe.
   - Record: attack vector, test file, command executed, exit code, result (DEFENDED / VULNERABLE), evidence.
   - Enforce tier minimums:
     - Critical: execute at least 3 probes.
     - Sensitive: execute at least 2 probes including Category 1 (Input Boundary) and the most relevant additional category.
     - Standard (impl): execute at least 1 probe using the most relevant category.
     - Standard (non-impl): no minimum probe count.
   - `[required]` vector coverage — this step defines coverage obligations; `attack-vectors.md` provides the tags. `[required]` marks minimum-coverage vectors; non-required vectors remain applicable and should be probed when relevant — the tag does not grant skip permission.
     - Critical / Sensitive: cover **all** `[required]` vectors within selected categories. For each: (a) execute a probe, or (b) document why it is non-applicable. Uncovered `[required]` vectors without documented rationale → `Overall Verdict: FAIL`.
     - Standard (impl): cover the **single most relevant** `[required]` vector in the selected category.
     - Standard (non-impl): no `[required]` coverage obligation.
5. **Compute Verdict**: `Overall Verdict: PASS` only when ALL attack probes result in DEFENDED. Any VULNERABLE → `Overall Verdict: FAIL`.
6. **Write Report**: Output to `...-task-<N>.adversarial.md`.
7. Write file paths in repository-relative form. If you mention a skill helper command, render it as `scripts/<name>.sh`, never an absolute filesystem path.

## Edge Cases

- **Zero applicable attack categories**: If the Selection Guidance table yields no relevant categories for the change area, apply tier-based fallbacks:
  - Critical / Sensitive: categories 1 (Input Boundary) and 2 (Error Handling) as baseline.
  - Standard (impl): category 1 (Input Boundary) only (1 probe minimum).
  - Standard (non-impl): user judgment (optional invocation).
  Record the rationale for limited applicability in the report.
- **Standard (impl) invocation**: The Adversarial Verify Input block is auto-generated (same as Sensitive/Critical). Tier minimums and `[required]` coverage rules are defined in Step 4.
- **Missing test infrastructure**: If the project lacks a test framework or runtime needed to execute attack probes, stop as `BLOCKED` and request the user to set up the necessary infrastructure. Do not skip attacks because tooling is absent.
- **Attack probe budget**:
  - Critical: minimum 3 probes, target 3-8, cap at 15.
  - Sensitive: minimum 2 probes, target 2-4, cap at 8.
  - Standard (impl): minimum 1 probe, target 1-2, cap at 4.
  - Standard (non-impl): choose probe count by scope and document rationale.

## On FAIL

- Task completion is revoked — the task is not considered done.
- The full chain must be re-executed: `execute-plan(implement)` → `execute-plan(dod-recheck)` → `adversarial-verify`.
- Report specific vulnerabilities with reproduction steps.
- After the FAIL→fix→re-execute chain completes with PASS, append each discovered vulnerability to `references/attack-vectors.md` under `## Project-Specific Vectors`. Format: `- **[Category]: [Vector Name]**: [Description and attack method]. Source: Task N, YYYY-MM-DD.`

## Output Format

```markdown
# <Topic> - Task <N> Adversarial Verification

## Verification Metadata

<digest-stamp.sh output>
- **Overall Verdict**: PASS | FAIL

## Attack Summary

| # | Category | Attack Vector | Required? | Test File | Command | Exit Code | Result | Evidence |
|---|----------|--------------|-----------|-----------|---------|-----------|--------|----------|
| 1 | [category] | [vector] | yes/no | [file] | `[command]` | [code] | DEFENDED/VULNERABLE | [brief evidence] |

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

For Critical-tier and Sensitive-tier tasks, completion requires ALL three conditions:

1. **Implement mode**: All RED/GREEN/REFACTOR/DoD steps pass.
2. **DoD Recheck mode**: Independent sub-agent confirms all DoD items pass.
3. **Adversarial Verify**: Independent sub-agent confirms all attack probes are defended.

If `adversarial-verify` returns FAIL, the implement completion is revoked and the full chain must be re-executed.

For Standard (non-impl) tasks, adversarial verification remains optional unless explicitly required by the user or plan. For Standard (impl) tasks, adversarial verification (1 probe) is conditionally mandatory.
