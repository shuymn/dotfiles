<!-- Do not restructure or delete sections. Update inline when behavior changes. -->

## Core Principles

- Execute only what is explicitly requested. No unrequested features, no "while we're at it" work.
- If requirements are ambiguous, ask before proceeding. Never guess.
- Do NOT maintain backward compatibility unless explicitly requested. Break things boldly.
- When implementation changes approved scope or design decisions, update the related Design Doc and ADR in the same task.
- Confirm interpretation in the current response language.
- Never hardcode values. Use configuration, environment variables, or constants.
- Use `uv run` for Python execution by default (including one-off scripts and tooling).
- Never compromise code quality to bypass errors (relaxing conditions, skipping tests, suppressing errors, temporary fixes). Always fix root causes.
- For non-trivial changes, ask "Would a staff engineer accept this?" and document rationale, impact scope, and verification evidence (relevant tests/logs/repro steps) before marking done.
- Prefer the most elegant solution that stays in scope: for non-trivial changes with material trade-offs, compare up to 2 alternatives and choose the lowest-risk option.
- If new findings invalidate the current plan, stop execution, update the plan, then continue.
- Do not expand scope to adjacent features without explicit approval.
- In the root session, use the design-doc / decompose-plan / execute-plan workflow only when the user explicitly requests it or provides its inputs; otherwise handle the request directly.
- In workflow mode, determine the active phase and explicitly delegate to the corresponding stage role; do not rely on automatic role selection.
- Keep user questioning in the root session for `design-doc(create)` and `decompose-plan(create)`.
- Run `design_reviewer`, `plan_reviewer`, `dod_rechecker`, `adversarial_verifier`, and `completion_auditor` with fresh context (`fork_context=false`).
- Keep production-code ownership with exactly one `task_implementer` at a time.
- Limit active sub-agents to at most 4 and use parallelism mainly for `repo_explorer` and `docs_researcher`.
- For long-running sub-agent work, silence alone is not evidence of a stall. Prefer waiting over interrupting; if agent-thread activity, local file changes, or command output indicates progress, keep waiting and avoid steering unless requirements changed or a real blocker is evident.
- Requirement Notation: Uses EARS (Easy Approach to Requirements Syntax) instead of BDD Given/When/Then for acceptance criteria. EARS is more context-efficient for LLM-driven workflows in a single-developer environment where non-technical stakeholder readability is unnecessary.

## Skill Usage Guide

If there is even a small chance a skill applies, invoke it BEFORE responding.

**Workflow:** Design needed → `design-doc(create)` → `design-doc(review)` | Task breakdown → `decompose-plan(create)` → `decompose-plan(review)` | Implementation → `execute-plan(implement)` → `execute-plan(dod-recheck)` → `adversarial-verify` → `completion-audit`

**Priority:** Process skills first (design-doc, decompose-plan), then implementation skills (execute-plan, domain-specific). Review/verification modes (`design-doc review`, `decompose-plan review`, `execute-plan dod-recheck`, `completion-audit`) run as independent sub-agents where applicable.

**Red flags — if you think any of these, stop and check skills:** "Just a simple question" / "Let me explore first" / "This skill is overkill" / "I remember this skill" (skills evolve; read current version).

**Discipline:** Rigid skills (TDD, verification) — follow exactly. Flexible skills (patterns) — adapt to context. The skill itself indicates which.

## Critical Recap

- Execute only what is explicitly requested.
- If requirements are ambiguous, ask before proceeding.
- Check applicable skills before responding.

<!-- Maintenance: Review this file when adding/removing skills or changing core workflow. Keep each line high-density — if it can be inferred from code or linters, remove it. -->
