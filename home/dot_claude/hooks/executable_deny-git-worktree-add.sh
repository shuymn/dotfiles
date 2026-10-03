#!/bin/sh
# Claude Code PreToolUse(Bash) hook: steer ad-hoc worktree creation to git-wt.
set -eu

PATH="/etc/profiles/per-user/$(id -un)/bin:/run/current-system/sw/bin:$PATH"
export PATH

command=$(jq -r '.tool_input.command // empty')
if printf '%s' "$command" | grep -Eq '(^|[^[:alnum:]_-])git([[:space:]]+-[^[:space:]]+([[:space:]]+[^-[:space:]][^[:space:]]*)?)*[[:space:]]+worktree[[:space:]]+add([[:space:]]|$)'; then
  jq -n '{hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: "Use `git wt --nocd <branch> [<start-point>]` (or `git -C <repo> wt --nocd ...`) instead of `git worktree add`; it applies the shared wt.basedir/wt.copy/wt.hook settings and prints the worktree path on the last line. For a detached checkout, create a branch name first."
  }}'
fi
