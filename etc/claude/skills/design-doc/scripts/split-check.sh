#!/usr/bin/env bash
set -euo pipefail

exec uv run python "$(dirname "$0")/../../_shared/scripts/split_check.py" "$@"
