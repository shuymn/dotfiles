# Global Coding Guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If requirements are ambiguous, ask before proceeding — never guess.
- If multiple interpretations exist, present them - don't pick silently. Confirm your interpretation in the current response language.
- If a simpler or more elegant approach exists, say so. Push back when warranted.
- For non-trivial changes with material trade-offs, compare up to 2 alternatives and choose the lowest-risk one.
- If something is unclear, stop. Name what's confusing. Ask.
- If new findings invalidate the current plan, stop, update the plan, then continue.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- Execute only what is explicitly requested - no unrequested features, no "while we're at it" work.
- Don't expand scope to adjacent features without explicit approval.
- No abstractions for single-use code. No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- Don't maintain backward compatibility unless explicitly requested. Break things boldly.
- Never hardcode values. Use configuration, environment variables, or constants.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Develop with TDD (exploration → Red → Green → Refactor). Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

- Never compromise code quality to bypass errors (relaxing conditions, skipping tests, suppressing errors, temporary fixes). Always fix root causes.
- When KPI or coverage targets are given, keep iterating until they are met.
- For non-trivial changes, ask "Would a staff engineer accept this?" and document rationale, impact scope, and verification evidence (tests/logs/repro steps) before marking done.
- When implementation changes approved scope or design decisions, update the related Design Doc and ADR in the same task.

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Code Design

- Maintain separation of concerns. Separate state from logic.
- Prioritize readability and maintainability.
- Define the contract layer (APIs/types) strictly, and keep the implementation layer regenerable.
- Express statically checkable rules in the environment's linter or ast-grep, not in prompts.

## Conventions & Operating Notes

- Use `uv run` for Python execution by default (including one-off scripts and tooling).
- Use EARS (Easy Approach to Requirements Syntax) instead of BDD Given/When/Then for acceptance criteria - more context-efficient for LLM-driven, single-developer workflows.
- For long-running sub-agent work, silence alone is not evidence of a stall. Prefer waiting over interrupting; if agent activity, file changes, or command output shows progress, keep waiting unless requirements changed or a real blocker is evident.

---

**Critical Recap:** Check applicable skills before responding. (See §1 for ambiguity handling, §2 for scope discipline.)

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
