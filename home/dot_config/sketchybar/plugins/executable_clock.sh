#!/bin/sh

sketchybar --set "$NAME" label="$(LC_TIME=C date '+%m/%d %a %H:%M:%S')"
