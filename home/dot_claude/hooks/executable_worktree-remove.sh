#!/bin/sh
# Claude Code WorktreeRemove hook: remove via `git wt -d`, which refuses dirty
# worktrees and keeps unmerged branches.
set -eu

PATH="$HOME/.local/share/mise/shims:/etc/profiles/per-user/$(id -un)/bin:/run/current-system/sw/bin:$PATH"
export PATH

path=$(jq -r '.worktree_path // empty')
[ -n "$path" ] || { echo "worktree-remove: missing worktree_path" >&2; exit 1; }
[ -d "$path" ] || exit 0

# Run from the main checkout; git-wt cannot delete the worktree it runs in.
common=$(git -C "$path" rev-parse --path-format=absolute --git-common-dir)
cd "$(dirname "$common")"
git wt -d "$path" >&2
