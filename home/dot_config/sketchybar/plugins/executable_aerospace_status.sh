#!/bin/sh

case "$NAME" in
*.mode)
  mode=$(aerospace list-modes --current 2>/dev/null || printf '?')

  case "$mode" in
  main)
    mode_label="N"
    mode_label_color=0xffc9d1d9
    mode_background_color=0xff3a4048
    ;;
  service)
    mode_label="S"
    mode_label_color=0xff1f2328
    mode_background_color=0xffff7b72
    ;;
  resize)
    mode_label="R"
    mode_label_color=0xff1f2328
    mode_background_color=0xff56d4dd
    ;;
  *)
    mode_label=$(printf '%s' "$mode" | cut -c1 | tr '[:lower:]' '[:upper:]')
    mode_label_color=0xff1f2328
    mode_background_color=0xffd2a8ff
    ;;
  esac

  sketchybar --set "$NAME" \
    label="$mode_label" \
    label.color="$mode_label_color" \
    background.color="$mode_background_color"
  ;;
*.layout)
  window_info=$(aerospace list-windows --focused --format '%{window-is-fullscreen}|%{window-layout}' 2>/dev/null || true)

  if [ -n "$window_info" ]; then
    old_ifs=$IFS
    IFS='|'
    # shellcheck disable=SC2086
    set -- $window_info
    IFS=$old_ifs

    is_fullscreen=$1
    layout=$2

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
    window_state="NONE"
    state_color=0xff8b949e
  fi

  sketchybar --set "$NAME" label="$window_state" label.color="$state_color"
  ;;
esac
