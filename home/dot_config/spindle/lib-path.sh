# shellcheck shell=sh

find_bin() {
  name=$1

  if [ -n "${SPINDLE_BIN:-}" ] && [ -x "$SPINDLE_BIN" ] && [ "$name" = spindle ]; then
    printf '%s\n' "$SPINDLE_BIN"
    return 0
  fi
  if [ -n "${SPINDLE_SKETCHYBAR_BIN:-}" ] && [ -x "$SPINDLE_SKETCHYBAR_BIN" ] && [ "$name" = spindle-sketchybar ]; then
    printf '%s\n' "$SPINDLE_SKETCHYBAR_BIN"
    return 0
  fi
  if command_path=$(command -v "$name" 2>/dev/null); then
    printf '%s\n' "$command_path"
    return 0
  fi
  username=${USER:-$(id -un 2>/dev/null || true)}
  if [ -n "$username" ] && [ -x "/etc/profiles/per-user/$username/bin/$name" ]; then
    printf '%s\n' "/etc/profiles/per-user/$username/bin/$name"
    return 0
  fi
  if [ -x "/run/current-system/sw/bin/$name" ]; then
    printf '%s\n' "/run/current-system/sw/bin/$name"
    return 0
  fi
  return 1
}

wait_for_spindle_socket() {
  spindle_socket=$1
  tries=${2:-120}
  interval=${3:-0.5}
  count=0

  while [ "$count" -lt "$tries" ]; do
    if [ -S "$spindle_socket" ]; then
      return 0
    fi
    count=$((count + 1))
    sleep "$interval"
  done

  return 1
}
