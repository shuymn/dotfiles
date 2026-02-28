<!-- Do not restructure or delete sections. Update inline when behavior changes. -->

## Core Principles

- Do NOT maintain backward compatibility unless explicitly requested. Break things boldly.
- Keep this file under 20-30 lines of instructions. Every line competes for the agent's limited context budget.
- Execute only what is explicitly requested. No unrequested features, no "while we're at it" work.
- When implementation changes approved scope or design decisions, update the related Design Doc and ADR in the same task.
- When requirements are ambiguous, ask via AskUserQuestionTool when available; otherwise ask a concise plain-text question before proceeding. Never guess.
- Confirm interpretation in the current response language (e.g., Japanese: 「私の理解は○○で正しいですか？」 / English: "Is my understanding that ○○ correct?").
- Never hardcode values. Use configuration, environment variables, or constants.
- Use `uv run` for Python execution by default (including one-off scripts and tooling).
- Never compromise code quality to bypass errors (relaxing conditions, skipping tests, suppressing errors, temporary fixes). Always fix root causes.
- For non-trivial changes, ask "Would a staff engineer accept this?" and document rationale, impact scope, and verification evidence (relevant tests/logs/repro steps) before marking done.
- Prefer the most elegant solution that stays in scope: for non-trivial changes with material trade-offs, compare up to 2 alternatives and choose the lowest-risk option.
- If new findings invalidate the current plan, stop execution, update the plan, then continue.
- Bad: User asks "Create a login function" → you add 2FA unrequested. Good: you ask about auth method, session management, and existing libraries first.

## Skill Usage Guide

If there is even a small chance a skill applies, invoke it BEFORE responding.

**Workflow:** Design needed → `design-doc` | Task breakdown → `decompose-plan` | Pre-execution audit → `analyze-plan` | Runtime prep → `setup-ralph` | Implementation → `execute-plan`

**Priority:** Process skills first (design-doc, decompose-plan, analyze-plan, setup-ralph), then implementation skills (execute-plan, domain-specific).

**Red flags — if you think any of these, stop and check skills:** "Just a simple question" / "Let me explore first" / "This skill is overkill" / "I remember this skill" (skills evolve; read current version).

**Discipline:** Rigid skills (TDD, verification) — follow exactly. Flexible skills (patterns) — adapt to context. The skill itself indicates which.

<!-- Maintenance: Review this file when adding/removing skills or changing core workflow. Keep each line high-density — if it can be inferred from code or linters, remove it. -->

@RTK.md
