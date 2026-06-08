#!/bin/sh

SPINDLE_EMIT="${SPINDLE_EMIT:-$HOME/.config/spindle/emit.sh}"
SPINDLE_STATE_DIR="${SPINDLE_STATE_DIR:-$HOME/.local/state/spindle}"
SPINDLE_LIB="${SPINDLE_LIB:-$HOME/.config/spindle/lib-path.sh}"

# shellcheck source=/dev/null
. "$SPINDLE_LIB"

invalidate_sketchybar_cache() {
  sketchybar_bin=$(find_bin spindle-sketchybar) || return 0
  "$sketchybar_bin" invalidate-cache --state-dir "$SPINDLE_STATE_DIR" >/dev/null 2>&1 || true
}

wait_for_spindle() {
  wait_for_spindle_socket "${SPINDLE_STATE_DIR}/spindle.sock"
}

wait_for_aerospace() {
  AEROSPACE_BIN=$(find_bin aerospace) || return 1
  export AEROSPACE_BIN
  tries=0

  while [ "$tries" -lt 40 ]; do
    if AEROSPACE_FOCUSED_WORKSPACE=$("$AEROSPACE_BIN" list-workspaces --focused 2>/dev/null); then
      export AEROSPACE_FOCUSED_WORKSPACE
      return 0
    fi
    tries=$((tries + 1))
    sleep 0.25
  done

  return 1
}

emit_aerospace_state() {
  SPINDLE_SOURCE=aerospace "$SPINDLE_EMIT" aerospace.mode.changed || true
  SPINDLE_SOURCE=aerospace "$SPINDLE_EMIT" aerospace.layout.changed || true
  if [ -z "${AEROSPACE_FOCUSED_WORKSPACE:-}" ] && [ -n "${AEROSPACE_BIN:-}" ]; then
    AEROSPACE_FOCUSED_WORKSPACE=$("$AEROSPACE_BIN" list-workspaces --focused 2>/dev/null || true)
    export AEROSPACE_FOCUSED_WORKSPACE
  fi
  SPINDLE_SOURCE=aerospace "$SPINDLE_EMIT" aerospace.workspace.changed || true
}

if [ ! -x "$SPINDLE_EMIT" ]; then
  exit 0
fi

wait_for_spindle || exit 0
wait_for_aerospace || exit 0
invalidate_sketchybar_cache
emit_aerospace_state
