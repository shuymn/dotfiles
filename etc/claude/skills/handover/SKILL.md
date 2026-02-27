---
name: handover
description: Creates or refreshes a HANDOVER.md file that captures current session state for the next assistant. Use when the user invokes /handover, when wrapping up a session, when context is getting full, when switching operators, or when the user asks for a handoff summary including decisions, pitfalls, lessons learned, next steps, and important files.
disable-model-invocation: true
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Create Session Handover

Generate a `HANDOVER.md` file in the current project folder so the next session can continue without losing context.

## Core Behavior

- Produce one actionable handover document, not a generic summary.
- Keep statements factual and verifiable.
- Do not invent details; mark unknowns explicitly.
- Prefer concise bullets with direct file and command references.

## Default Output Location

- Write to `HANDOVER.md` in the current working project.
- If the user specifies another path or filename, follow the user request.

## Workflow

1. Gather session context.
   - Review completed work, pending work, and user goals from the conversation.
   - Inspect repository context when available:
     - `rtk git status`
     - `git branch --show-current`
     - `rtk git log -n 15`
     - `rtk git diff`
2. Extract handover essentials.
   - What was completed.
   - What is still in progress.
   - Key decisions and rationale.
   - Pitfalls, bugs, and applied fixes/workarounds.
   - Lessons learned and recurring gotchas.
   - Important files and why each matters.
   - Clear next actions in execution order.
3. Write `HANDOVER.md` using the template below.
4. Run a final quality pass.
   - Ensure every claim is specific.
   - Ensure all referenced files/commands exist or are marked as assumptions.
   - Ensure next steps are concrete and immediately executable.
5. Save and report completion.
   - Confirm the file path.
   - Highlight the highest-priority next step.

## HANDOVER.md Template

```markdown
# Session Handover

## 1. Session Snapshot
- Date:
- Project:
- Primary goal:
- Current status:

## 2. Completed Work
- [Completed item with evidence: file/command/commit]

## 3. In-Progress Work
- [Work item]
- Current state:
- Remaining tasks:

## 4. Key Decisions (and Why)
- Decision:
  - Why:
  - Alternatives considered:
  - Impact:

## 5. Problems, Pitfalls, and Fixes
- Problem:
  - Symptoms:
  - Root cause (if known):
  - Fix/workaround:
  - Validation:

## 6. Lessons Learned / Gotchas
- [Lesson]
- [Gotcha and prevention]

## 7. Important Files Map
- `path/to/file`: Why this file matters and its current state
- `path/to/file`: Why this file matters and its current state

## 8. Next Steps (Ordered)
1. [Highest-priority action]
2. [Next action]
3. [Follow-up action]

## 9. Open Questions / Risks
- [Question or risk]
- [Required decision or mitigation]

## 10. Useful Commands / References
- `command`: Purpose
- [Reference link or doc path]
```

## Quality Bar

- Write for a new session with no prior memory.
- Prefer "what changed + why it matters" over raw logs.
- Include blockers and assumptions explicitly.
- Keep output concise but complete enough to resume work in under 30 minutes.
- If little or no work happened, still generate the document and say so clearly.

## Optional Additions

- Add a "Recent Commits" subsection when commits exist.
- Add a "Validation/Test Results" subsection when tests were run.
- Add deployment/release status when environment changes were made.
