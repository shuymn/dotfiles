#!/bin/sh

workspace=${NAME##*.}
focused_workspace=$(aerospace list-workspaces --focused 2>/dev/null || printf '')
window_count=$(aerospace list-windows --workspace "$workspace" --count 2>/dev/null || printf '0')

if [ "$window_count" -gt 0 ] 2>/dev/null; then
  label="$workspace:$window_count"
else
  label="$workspace"
fi

if [ "$workspace" = "$focused_workspace" ]; then
  label_color=0xffffffff
  background_drawing=on
  background_color=0xff1f6feb
else
  label_color=0xff8b949e
  background_drawing=off
  background_color=0xff1f2328
fi

sketchybar --set "$NAME" \
  label="$label" \
  label.color=$label_color \
  background.drawing=$background_drawing \
  background.color=$background_color
