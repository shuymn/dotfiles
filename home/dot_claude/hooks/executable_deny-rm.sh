#!/bin/sh
# Claude Code PreToolUse(Bash) hook: steer deletions to the Trash so they can be restored.
# Settings run it only when `if: Bash(rm *)` matches, but Claude Code also runs it
# when it cannot parse the command, so it checks for an rm command word itself.
set -eu

PATH="/etc/profiles/per-user/$(id -un)/bin:/run/current-system/sw/bin:$PATH"
export PATH

command=$(jq -r '.tool_input.command // empty')
if printf '%s' "$command" | grep -Eq '(^|[;&|`]|\$\()[[:space:]]*((command|builtin|nohup|nice|time)[[:space:]]+)*rm([[:space:]]|$)'; then
  # shellcheck disable=SC2016 # the backticks are literal Markdown
  jq -n '{hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: "Use `trash <path>...` instead of `rm`; it moves files and directories to the Trash so a mistaken deletion can be restored (no -r/-f flags needed). Remove Git worktrees with `git wt -d <branch|path>`, which refuses a dirty worktree and keeps an unmerged branch; for a throwaway worktree, `git wt -D <branch|path>` also moves it to the Trash and deletes its branch."
  }}'
fi
