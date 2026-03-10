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
- For long-running sub-agent work, silence alone is not evidence of a stall. Prefer waiting over interrupting; if agent-thread activity, local file changes, or command output indicates progress, keep waiting and avoid steering unless requirements changed or a real blocker is evident.
- Requirement Notation: Uses EARS (Easy Approach to Requirements Syntax) instead of BDD Given/When/Then for acceptance criteria. EARS is more context-efficient for LLM-driven workflows in a single-developer environment where non-technical stakeholder readability is unnecessary.

## Development Style

- Develop with TDD (exploration → Red → Green → Refactoring).
- When KPI or coverage targets are given, keep iterating until they are met.

## Code Design

- Maintain separation of concerns.
- Separate state from logic.
- Prioritize readability and maintainability.
- Define the contract layer (APIs/types) strictly, and keep the implementation layer regenerable.

## Critical Recap

- Execute only what is explicitly requested.
- If requirements are ambiguous, ask before proceeding.
- Check applicable skills before responding.

<!-- Maintenance: Review this file when adding/removing skills or changing core workflow. Keep each line high-density — if it can be inferred from code or linters, remove it. -->
