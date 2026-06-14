#!/bin/sh
# Verify that top-level mise [tools] entries in config.toml are present in
# mise.lock with the same locked version.
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH='' cd -- "$script_dir/.." && pwd)

config=${1:-"$repo/home/dot_config/mise/config.toml"}
lock=${2:-"$repo/home/dot_config/mise/mise.lock"}
checker="$script_dir/check-mise-lock-consistency.py"

if [ ! -f "$config" ] || [ ! -f "$lock" ]; then
  echo "usage: $0 [mise-config.toml] [mise.lock]" >&2
  echo "missing config or lockfile: $config / $lock" >&2
  exit 2
fi

find_python() {
  if [ -n "${PYTHON:-}" ]; then
    printf '%s\n' "$PYTHON"
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  fi
}

python_bin=$(find_python || true)
if [ -z "$python_bin" ]; then
  echo "python3 is required to parse mise TOML" >&2
  exit 2
fi

exec "$python_bin" "$checker" "$config" "$lock"
