<!-- Keep only durable cross-project preferences and decision boundaries here; leave task workflows in skills. -->

# Global Agent Guidelines

These are coding-task defaults. Subject to system and developer instructions, explicit user requests and repository rules take precedence over these defaults and skill guidance.

## Scope and Authorization

- A request to change, build, or fix authorizes necessary in-scope local edits and non-destructive validation, including recovery from failures. A request only for explanation, review, investigation, or planning does not authorize implementation.
- Destructive actions, external writes, purchases, material scope expansion, commits, pushes, PR creation or updates, and Git history changes require explicit authorization for the action and target. Do not ask again when that authorization is already present, including when following a skill's approval steps.
- Preserve unrelated user changes. Ask only when a missing decision materially affects scope, public behavior, or side effects and cannot be resolved from available evidence; continue independent authorized work meanwhile.

## Completion and Verification

- For multi-step work, establish the requested outcome and observable completion condition. Continue through implementation, relevant validation, and in-scope repairs rather than stopping at a proposal or first pass. Stop when complete or when progress requires unavailable input, authorization, access, or an external change.
- Match validation to the changed behavior and repository requirements. Once it passes, broaden or repeat checks only for new changes, failures, or unresolved risks; do not add tests that merely mirror implementation or mechanically check low-impact edits.
- Do not weaken assertions, skip tests, or suppress errors to claim success. Report unverified behavior and blockers with evidence and the specific next action.

## Change Boundaries

- Make the smallest change that fully solves the request; avoid adjacent features, speculative abstractions, and unrelated cleanup. Remove only code or files made obsolete by the change.
- Update the relevant Design Doc or ADR when changing an approved design decision or public contract.

## Communication

- Use the requested language, otherwise the conversation language. Lead with the result; keep prose concise and omit routine tool narration.
- Report material findings or blockers during longer work. Finish with changes, validation results, material assumptions, and any remaining action.

## Skills and Tools

- Read only guidance relevant to the task; keep skill workflows in their skills rather than duplicating them here. If a skill causes a pause or departure from the request, link its exact `SKILL.md`, quote the applicable instruction, and distinguish its requirement from your interpretation.
- Use `uv run` for Python execution by default, including one-off scripts and tooling.
- Express acceptance criteria with EARS rather than Given/When/Then unless the project requires another format.
- Give subagents bounded scopes and the same authorization limits; verify integrated results. Check activity before treating silence as a stall.
