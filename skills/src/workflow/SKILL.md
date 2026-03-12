---
name: workflow
description: >-
  Use when the user invokes /workflow.
  Injects project workflow methodology as context.
  Accepts argument: plan, exec, review (default: all).
disable-model-invocation: true
allowed-tools: [Read]
---

## Path Resolution

- `<skill-root>` means the directory containing this `SKILL.md`.
- Resolve `references/...` relative to `<skill-root>`, not the caller's current working directory.

## Argument Dispatch

Determine which reference files to read from `$ARGUMENTS`:

- If `$ARGUMENTS` starts with `plan` → read [references/plan.md](references/plan.md) only
- If `$ARGUMENTS` starts with `exec` → read [references/exec.md](references/exec.md) only
- If `$ARGUMENTS` starts with `review` → read [references/review.md](references/review.md) only
- If `$ARGUMENTS` is empty or unrecognized → read all three files: [references/plan.md](references/plan.md), [references/exec.md](references/exec.md), [references/review.md](references/review.md)

Read the matched file(s) and present their contents as workflow context for the current session.
