#!/bin/sh
# Claude Code PostCompact hook: append each compaction summary to a JSONL log so
# later problems can be checked against what the summary kept or dropped.
# Log: ${XDG_STATE_HOME:-~/.local/state}/claude/compactions.jsonl, one JSON object per compaction,
# appended, never rotated. Fields: ts (UTC time of the hook run, ISO 8601), and session_id, trigger
# (manual or auto), cwd, transcript_path and compact_summary copied from the PostCompact payload
# (null when the payload lacks one). The hiden retrospective reads it (references/retro.md).
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
