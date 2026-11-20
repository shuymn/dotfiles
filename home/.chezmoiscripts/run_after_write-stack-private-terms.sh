#!/bin/sh
# Write ~/.config/stack/private-terms from host.toml and ~/.claude/kaizen/private-terms on every apply. A script, not a
# template, so no private value appears in `chezmoi diff` or the apply plan.
set -eu
if ! command -v uv >/dev/null 2>&1; then
  # The first converge runs chezmoi before mise installs uv; the next apply writes the file.
  echo "write-stack-private-terms: uv not found; ~/.config/stack/private-terms not written" >&2
  exit 0
fi
exec uv run --script "$CHEZMOI_WORKING_TREE/scripts/stack-private-terms"
