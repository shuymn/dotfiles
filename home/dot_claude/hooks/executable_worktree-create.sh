#!/bin/sh
# Claude Code WorktreeCreate hook: delegate worktree creation to git-wt so
# Claude-created worktrees share wt.basedir / wt.copy / wt.hook with the shell.
# Prints the worktree path as the last stdout line; everything else goes to stderr.
set -eu

# GUI-launched clients (Claude Desktop) may start with a minimal PATH.
PATH="$HOME/.local/share/mise/shims:/etc/profiles/per-user/$(id -un)/bin:/run/current-system/sw/bin:$PATH"
export PATH

input=$(cat)
name=$(printf '%s' "$input" | jq -r '.name // empty')
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -n "$name" ] || { echo "worktree-create: missing name" >&2; exit 1; }
[ -n "$cwd" ] && cd "$cwd"

# Match worktree.baseRef=fresh: branch from the remote default branch.
git fetch --quiet origin >&2 || echo "worktree-create: fetch failed; using cached origin refs" >&2
start=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || echo HEAD)

path=$(git wt --nocd "$name" "$start" | tail -n 1)
[ -d "$path" ] || { echo "worktree-create: git wt returned no directory: $path" >&2; exit 1; }
printf '%s\n' "$path"
