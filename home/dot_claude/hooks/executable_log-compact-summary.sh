#!/bin/sh
# Claude Code PostCompact hook: append each compaction summary to a JSONL log so
# later problems can be checked against what the summary kept or dropped.
set -eu

PATH="/etc/profiles/per-user/$(id -un)/bin:/run/current-system/sw/bin:$PATH"
export PATH

log="${XDG_STATE_HOME:-$HOME/.local/state}/claude/compactions.jsonl"
mkdir -p "$(dirname "$log")"
jq -c '{
  ts: (now | todate),
  session_id,
  trigger,
  cwd,
  transcript_path,
  compact_summary
}' >>"$log"
