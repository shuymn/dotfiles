#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  printf 'usage: %s <event-type> [json-data]\n' "$0" >&2
  exit 64
fi

event_type=$1
data=${2:-}
SPINDLE_LIB="${SPINDLE_LIB:-$HOME/.config/spindle/lib-path.sh}"

# shellcheck source=/dev/null
. "$SPINDLE_LIB"

if [ -z "${JQ_BIN:-}" ]; then
  JQ_BIN=$(find_bin jq) || {
    printf 'jq not found in PATH, user profile, or system profile\n' >&2
    exit 69
  }
fi

if [ -z "$data" ]; then
  case "$event_type" in
    aerospace.workspace.changed)
      if [ -n "${AEROSPACE_FOCUSED_WORKSPACE:-}" ]; then
        # shellcheck disable=SC2016 # jq filter variables are intentionally single-quoted.
        data=$("$JQ_BIN" -cn --arg focused_workspace "$AEROSPACE_FOCUSED_WORKSPACE" '{focused_workspace:$focused_workspace}')
      fi
      ;;
    sketchybar.workspace.clicked)
      if [ -n "${WORKSPACE:-}" ]; then
        # shellcheck disable=SC2016 # jq filter variables are intentionally single-quoted.
        data=$("$JQ_BIN" -cn --arg workspace "$WORKSPACE" '{workspace:$workspace}')
      fi
      ;;
  esac
fi

if [ -z "$data" ]; then
  data="{}"
fi

source=${SPINDLE_SOURCE:-${event_type%%.*}}
if [ "$source" = "$event_type" ]; then
  source=spindle-hook
fi

if [ -z "${SPINDLE_BIN:-}" ]; then
  SPINDLE_BIN=$(find_bin spindle) || {
    printf 'spindle not found in PATH, user profile, or system profile\n' >&2
    exit 69
  }
fi

# shellcheck disable=SC2016 # jq filter variables are intentionally single-quoted.
request=$("$JQ_BIN" -cn \
  --arg type "$event_type" \
  --arg source "$source" \
  --argjson data "$data" \
  '{command:"emit",type:$type,source:$source,data:$data}')
"$SPINDLE_BIN" send --request "$request" >/dev/null 2>&1
