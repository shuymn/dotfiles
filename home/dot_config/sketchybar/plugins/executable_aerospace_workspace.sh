#!/bin/sh

WORKSPACES="1 2 3 4 5 6 7 8 9 10"
AEROSPACE_STATE_DIR="${TMPDIR:-/tmp}/sketchybar-aerospace"
STATE_FILE="$AEROSPACE_STATE_DIR/workspaces.state"

is_occupied() {
  case "$1" in
  *" $2 "*) return 0 ;;
  *) return 1 ;;
  esac
}

render_workspace() {
  workspace=$1
  role=$2
  label=$workspace

  if [ "$workspace" = 10 ]; then
    label=0
  fi

  case "$role" in
  active)
    label_color=0xff1f2328
    label_font="SF Pro Text:Semibold:13.0"
    background_drawing=on
    background_color=0xffd2a8ff
    ;;
  occupied)
    label_color=0xffc9d1d9
    label_font="SF Pro Text:Medium:13.0"
    background_drawing=on
    background_color=0xff3a4048
    ;;
  *)
    label_color=0xff8b949e
    label_font="SF Pro Text:Medium:13.0"
    background_drawing=off
    background_color=0xff1f2328
    ;;
  esac

  printf " --set aerospace.workspace.%s label=%s label.color=%s label.font='%s' label.width=24 label.align=center label.padding_left=0 label.padding_right=0 background.drawing=%s background.color=%s" \
    "$workspace" \
    "$label" \
    "$label_color" \
    "$label_font" \
    "$background_drawing" \
    "$background_color"
}

collect_windows() {
  aerospace list-windows --all --format '%{workspace}' 2>/dev/null || true
}

focused_workspace() {
  aerospace list-workspaces --focused 2>/dev/null || printf ''
}

previous_snapshot() {
  [ -r "$STATE_FILE" ] && cat "$STATE_FILE"
}

write_snapshot() {
  snapshot=$1
  tmp_file="$STATE_FILE.$$"
  mkdir -p "$AEROSPACE_STATE_DIR" || return 1
  printf '%s' "$snapshot" >"$tmp_file" && mv "$tmp_file" "$STATE_FILE"
}

windows_occupied_set() {
  printf '%s\n' "$1" | awk -v workspaces="$WORKSPACES" '
    NF { seen[$1] = 1 }
    END {
      n = split(workspaces, ordered, " ")
      for (i = 1; i <= n; i++) {
        if (seen[ordered[i]]) printf " %s ", ordered[i]
      }
    }
  '
}

render_current_state() {
  active_workspace=${FOCUSED_WORKSPACE:-$(focused_workspace)}
  windows=$(collect_windows)
  occupied=$(windows_occupied_set "$windows")
  snapshot=$(printf '%s\n%s\n' "$active_workspace" "$occupied")

  if [ "$snapshot" = "$(previous_snapshot)" ]; then
    return 0
  fi

  command=sketchybar

  for workspace in $WORKSPACES; do
    role=empty

    if [ "$workspace" = "$active_workspace" ]; then
      role=active
    elif is_occupied "$occupied" "$workspace"; then
      role=occupied
    fi

    command="$command$(render_workspace "$workspace" "$role")"
  done

  eval "$command" && write_snapshot "$snapshot"
}

# Let AeroSpace settle after workspace changes, then paint one authoritative
# snapshot in a single SketchyBar batch. FOCUSED_WORKSPACE from AeroSpace is
# used when available.
if [ "$SENDER" = aerospace_workspace_change ]; then
  sleep 0.05
fi

render_current_state
