#!/bin/sh

SPINDLE_LIB="${SPINDLE_LIB:-$HOME/.config/spindle/lib-path.sh}"

# shellcheck source=/dev/null
. "$SPINDLE_LIB"

if ! spindle_bin=$(find_bin spindle); then
  exit 0
fi

"$spindle_bin" send --request '{"command":"invoke","action":"clock.render","source":"sketchybar","capabilities":[],"args":{"name":"clock"}}' >/dev/null 2>&1 || exit 0
