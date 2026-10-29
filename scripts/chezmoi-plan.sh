#!/bin/sh
# Usage: chezmoi-plan.sh <chezmoi command...>
# Summarize what `chezmoi apply` would do per target, then show the diff
# without lockfiles, whose generated churn says nothing about the change.
set -eu

# Collect everything before display so a chezmoi failure fails the command.
status=$("$@" status)
if [ -z "$status" ]; then
  echo "Nothing to apply."
  exit 0
fi
diff=$("$@" diff --no-pager)
pager=$("$@" execute-template '{{ .chezmoi.config.diff.pager }}')
if [ -t 1 ]; then
  # delta writes into a pipe here, so it cannot see the terminal width itself.
  case $pager in
  delta*) pager="$pager --width=$(tput cols)" ;;
  esac
fi

plan() {
  echo "== chezmoi apply plan"
  # Column 1: home changed since chezmoi last wrote it; column 2: what apply does.
  printf '%s\n' "$status" | while IFS= read -r line; do
    target=${line#???}
    case $line in
    [!\ ][!\ ]*)
      # Apply overwrites modify_ targets without asking, so they are not conflicts.
      source=$("$@" source-path "$HOME/$target")
      case ${source##*/} in
      modify_*) line=" ${line#?}" ;;
      esac
      ;;
    esac
    case $line in
    [!\ ][!\ ]*) action="conflict: edited in home since the last apply; apply asks before overwriting" ;;
    ?A*) action="add" ;;
    ?D*) action="delete" ;;
    ?M*.lock) action="update (lockfile, diff omitted)" ;;
    ?M*) action="update" ;;
    ?R*) action="run script" ;;
    *) continue ;;
    esac
    printf '  %-40s %s\n' "$target" "$action"
  done
  echo
  echo "== diff (left: current home, right: after apply)"
  printf '%s\n' "$diff" | awk '/^diff --git / { skip = $NF ~ /\.lock$/ } !skip' | ${pager:-cat}
}

if [ -t 1 ]; then
  plan "$@" | less -RFX
else
  plan "$@"
fi
