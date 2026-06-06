#!/bin/sh

WORKSPACES="1 2 3 4 5 6 7 8 9 10"

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

windows_occupied_set() {
  printf '%s\n' "$1" | awk 'NF { seen[$1] = 1 } END { for (workspace in seen) printf " %s ", workspace }'
}

workspace_window_count() {
  printf '%s\n' "$1" | awk -v workspace="$2" '$1 == workspace { count++ } END { print count + 0 }'
}

render_current_state() {
  active_workspace=${FOCUSED_WORKSPACE:-$(focused_workspace)}
  windows=$(collect_windows)
  occupied=$(windows_occupied_set "$windows")
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

  eval "$command"
}

optimistic_previous_role() {
  workspace=$1
  transition=$2
  windows=$3
  count=$(workspace_window_count "$windows" "$workspace")

  if [ "$transition" = move ]; then
    count=$((count - 1))
  fi

  if [ "$count" -gt 0 ] 2>/dev/null; then
    printf occupied
  else
    printf empty
  fi
}

render_optimistic_state() {
  target_workspace=$1
  transition=${2:-focus}
  current_workspace=$(focused_workspace)
  command=sketchybar

  if [ -n "$current_workspace" ] && [ "$current_workspace" != "$target_workspace" ]; then
    windows=$(collect_windows)
    previous_role=$(optimistic_previous_role "$current_workspace" "$transition" "$windows")
    command="$command$(render_workspace "$current_workspace" "$previous_role")"
  fi

  command="$command$(render_workspace "$target_workspace" active)"
  eval "$command"
}

case "$1" in
optimistic)
  [ -n "$2" ] || exit 0
  render_optimistic_state "$2" "$3"
  ;;
*)
  # Let AeroSpace settle, then paint one authoritative snapshot in a single
  # SketchyBar batch. FOCUSED_WORKSPACE from AeroSpace is used when available.
  sleep 0.05
  render_current_state
  ;;
esac
