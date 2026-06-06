#!/bin/sh

mode=$(aerospace list-modes --current 2>/dev/null || printf '?')
workspace=$(aerospace list-workspaces --focused 2>/dev/null || printf '?')
window_info=$(aerospace list-windows --focused --format '%{window-is-fullscreen}|%{window-layout}|%{app-name}' 2>/dev/null || true)

if [ -n "$window_info" ]; then
  old_ifs=$IFS
  IFS='|'
  # shellcheck disable=SC2086
  set -- $window_info
  IFS=$old_ifs

  is_fullscreen=$1
  layout=$2
  app_name=$3

  if [ "$is_fullscreen" = "true" ]; then
    window_state="FULL"
    state_color=0xffd29922
  else
    case "$layout" in
    *floating*)
      window_state="FLOAT"
      state_color=0xffa371f7
      ;;
    *accordion*)
      window_state="ACCORD"
      state_color=0xff58a6ff
      ;;
    *)
      window_state="TILE"
      state_color=0xff3fb950
      ;;
    esac
  fi
else
  app_name="no window"
  window_state="NONE"
  state_color=0xff8b949e
fi

if [ "$mode" = "main" ]; then
  mode_color=0xff8b949e
else
  mode_color=0xffff7b72
fi

sketchybar --set "$NAME" \
  icon="mode:$mode" \
  icon.color="$mode_color" \
  label="ws:$workspace $window_state $app_name" \
  label.color="$state_color"
