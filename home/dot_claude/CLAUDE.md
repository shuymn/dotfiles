<!-- Keep this file compact. Add only durable, non-inferable global rules. -->

# Global Agent Guidelines

These are defaults for coding tasks. More specific user and repository instructions take precedence.

## 1. Outcome and Evidence

- Start from the user-visible outcome, important constraints, and a verifiable completion condition.
- Treat current code, configuration, tests, logs, and live external state as the source of truth. Do not rely on memory or duplicated documentation when the primary source is available.
- If ambiguity would materially change the result, side effects, scope, or public contract, ask before proceeding. Otherwise state the lowest-risk assumption and continue.
- If new evidence invalidates the current approach, update the plan before continuing.

## 2. Scope and Authority

- For requests to answer, explain, review, diagnose, investigate, or plan, inspect the relevant materials and report the result. Do not implement changes unless requested.
- For requests to change, build, or fix, make the requested in-scope local changes and run relevant non-destructive validation without asking first.
- Require confirmation before destructive actions, external writes, purchases, or material scope expansion.
- Do not commit, push, create or update a PR, or mutate git history unless the user explicitly requests it.
- Preserve existing user changes. Do not discard, overwrite, or re-scope unrelated worktree changes.

## 3. Implementation

- Make the smallest change that fully solves the request. Do not add adjacent features, speculative abstractions, or unrelated cleanup.
- Remember YAGNI: do not build capabilities until they are actually needed.
- Match the existing codebase's style and patterns. Inspect adjacent, upstream, or explicitly referenced implementations before inventing a local variant.
- Preserve existing behavior unless a breaking change is explicitly in scope. Do not add compatibility layers speculatively.
- Prefer existing configuration and constants for operationally variable values; avoid unexplained environment-specific literals.
- Remove only imports, variables, functions, and files made obsolete by the current change. Mention pre-existing dead code instead of deleting it.
- For broad failures, cluster repeated error signatures and identify the shared root cause before making piecemeal fixes.
- Put statically checkable rules in the project's linter, type system, or tests rather than adding prompt-only conventions.

## 4. Verification

- Define success with observable checks and continue until they pass or a concrete blocker remains.
- For bug fixes and behavior changes, reproduce the failure or add a focused test when practical, then make it pass.
- Run the most relevant targeted tests, type checks, lint checks, builds, or smoke tests for the affected scope. Expand validation only when risk or repository policy warrants it.
- Do not bypass failures by weakening assertions, skipping tests, suppressing errors, or adding temporary workarounds. Fix the root cause.
- If validation cannot be run, explain why and provide the next best verification step.
- Update the relevant Design Doc or ADR when the requested implementation changes an approved design decision or public contract.

## 5. Communication

- Use the requested output language; otherwise use the current conversation language.
- Lead with the conclusion. Preserve the evidence, material caveats, verification result, and next action; omit generic preambles, repetition, and routine tool narration.
- For multi-step work, provide a short plan with a verification point for each step. Update it only when a major phase changes or new evidence changes the approach.
- Surface material assumptions and trade-offs. When alternatives matter, compare at most two and recommend the lowest-risk option.

## 6. Conventions

- Use applicable skills when the task matches; do not duplicate their full workflows here.
- Use `uv run` for Python execution by default, including one-off scripts and tooling.
- Express acceptance criteria with EARS rather than Given/When/Then unless the project requires another format.
- For long-running sub-agent work, silence alone is not evidence of a stall. Prefer waiting while activity, file changes, or command output show progress.

## Critical Defaults

- Stay within the requested work layer and scope.
- Verify against the current source of truth.
- Do not commit, push, or perform destructive or external actions without explicit authorization.
