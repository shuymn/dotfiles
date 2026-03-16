---
name: adversarial-verify
description: "Adversarial verification of code changes — probes target files for vulnerabilities through edge cases, error paths, security boundaries, and concurrency attacks. Use when you want to stress-test implementation correctness or validate defensive robustness before shipping."
allowed-tools: [Read, Bash, Grep, Glob, Write]
---

## Path Resolution

- `<skill-root>` means the directory containing this `SKILL.md`.
- Resolve `scripts/...` and `references/...` relative to `<skill-root>`, not the caller's current working directory.
- When executing local helpers, use explicit paths such as `<skill-root>/scripts/...`.

## Constraints

- Do NOT modify implementation code. Write only the adversarial report and attack test files. Reason: modifying code during adversarial verification would invalidate evidence and conflate "finding vulnerabilities" with "fixing them."
- Attack test files must be clearly separated from production tests (use a dedicated directory or naming convention such as `*_adversarial_test.*`).

## Precondition Check

Before starting adversarial verification, confirm preconditions:

1. Verify all target files exist in the repository. If any target file is missing, stop as `BLOCKED`.
2. Verify `<skill-root>/references/attack-vectors.md` exists. If missing, stop as `BLOCKED`.

## Tier-Based Invocation Policy

| Risk Tier | Invocation | Minimum Probes | Attack Scope |
|-----------|------------|----------------|--------------|
| Critical | Mandatory | 3 | All applicable categories |
| Sensitive | Mandatory | 2 | Category 1 (Input Boundary) + most relevant 1 additional category |
| Standard (impl) | Conditional Mandatory | 1 | Most relevant 1 category |
| Standard (non-impl) | Optional | — | User-selected |

**Implementation file definition**: Standard (impl) applies when at least one target file is implementation code rather than docs/tests-only scaffolding.

## Input

- **Target files** (required): Repository-relative paths of files to verify.
- **Change description** (required): Description of what changed, its impact scope, and the rationale behind the change.
- **Risk tier** (optional): Critical / Sensitive / Standard. Defaults to Sensitive when omitted.

## Procedure

1. **Generate Header**: Write verification metadata directly:
   - **Mode**: adversarial-verify
   - **Target Files**: list of target files
   - **Risk Tier**: Critical / Sensitive / Standard
   - **Verified At**: UTC timestamp (obtain via `date -u +"%Y-%m-%dT%H:%M:%SZ"`)
2. **Load Context**: Read all user-provided target files and `<skill-root>/references/attack-vectors.md` (including the optional `## Maintainer-Curated Extension Vectors` section when present).
3. **Select Attack Categories**: Based on the change description and the content of target files, select applicable attack categories from the reference. Do NOT blindly apply all categories — choose only those relevant to the actual change. If `## Maintainer-Curated Extension Vectors` contains vectors matching the change characteristics, include them as additional probe targets regardless of the selected categories.
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
5. **Coverage Gate**: Verify `[required]` vector coverage procedurally:
   - Identify all `[required]` vectors within selected categories from `attack-vectors.md`.
   - Cross-reference each against the Attack Summary table entries.
   - Standard: no `[required]` coverage obligation — proceed.
   - Sensitive / Critical: if any `[required]` vector is uncovered without documented N/A rationale → `Overall Verdict: FAIL`.
6. **Compute Verdict**: `Overall Verdict: PASS` only when ALL attack probes result in DEFENDED and the Coverage Gate is PASS. Any VULNERABLE or coverage FAIL → `Overall Verdict: FAIL`.
7. **Write Report**: Output to `adversarial-report.md`.
8. Write file paths in repository-relative form. If you mention a skill helper command, render it as `scripts/<name>.sh`, never an absolute filesystem path.

## Edge Cases

- **Zero applicable attack categories**: If the Selection Guidance table yields no relevant categories for the change area, apply tier-based fallbacks:
  - Critical / Sensitive: categories 1 (Input Boundary) and 2 (Error Handling) as baseline.
  - Standard (impl): category 1 (Input Boundary) only (1 probe minimum).
  - Standard (non-impl): user judgment (optional invocation).
  Record the rationale for limited applicability in the report.
- **Missing test infrastructure**: If the project lacks a test framework or runtime needed to execute attack probes, stop as `BLOCKED` and request the user to set up the necessary infrastructure. Do not skip attacks because tooling is absent.
- **Attack probe budget**:
  - Critical: minimum 3 probes, target 3-8, cap at 15.
  - Sensitive: minimum 2 probes, target 2-4, cap at 8.
  - Standard (impl): minimum 1 probe, target 1-2, cap at 4.
  - Standard (non-impl): choose probe count by scope and document rationale.

## On FAIL

- Report specific vulnerabilities with reproduction steps.
- The user is responsible for fixing identified vulnerabilities and re-running adversarial verification.
- If the run reveals a reusable attack vector, record it in the adversarial report and propose a separate skill-maintenance task. Do NOT edit `<skill-root>/references/attack-vectors.md` during adversarial verification.

## Output Format

```markdown
# Adversarial Verification Report

## Verification Metadata

- **Mode**: adversarial-verify
- **Target Files**: [list]
- **Risk Tier**: [tier]
- **Verified At**: [UTC timestamp]
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

- Adversarial verification: PASS/FAIL
- Reason: [rationale]
```
