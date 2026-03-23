#!/usr/bin/env bash
set -Eeu -o pipefail

# ── Icons (edit these to add Nerd Font glyphs) ──────────────────
ICON_MODEL="󰚩"
ICON_BRANCH=""

# ── Style constants ──────────────────────────────────────────────
R='\033[0m'
BOLD='\033[1m'
RED='\033[31m'
CYAN='\033[36m'
YELLOW='\033[33m'
MAGENTA='\033[35m'
SEP=" | "

# ── Primitives ───────────────────────────────────────────────────

# Green(0%) -> Yellow(mid%) -> Red(100%) gradient
# Usage: gradient <pct> [mid]  (mid defaults to 50)
gradient() {
  local pct=$1 mid=${2:-50}
  if [ "$pct" -lt "$mid" ]; then
    printf '\033[38;2;%d;200;80m' "$((pct * 255 / mid))"
  else
    local range=$((100 - mid))
    local g=$((200 - (pct - mid) * 200 / range))
    printf '\033[38;2;255;%d;60m' "$((g > 0 ? g : 0))"
  fi
}

# Colored dot with percentage: ● 42%
# Usage: dot <pct> [cap] [mid]  (cap defaults to 100, mid to 50; both in display %)
dot() {
  local pct
  pct=$(printf '%.0f' "$1")
  local cap=${2:-100} mid=${3:-50}
  local scaled=$((pct * 100 / cap))
  if [ "$scaled" -gt 100 ]; then
    scaled=100
  fi
  local scaled_mid=$((mid * 100 / cap))
  printf '%s●%s %s%s%%%s' "$(gradient "$scaled" "$scaled_mid")" "$R" "$BOLD" "$pct" "$R"
}

# Append a labeled dot segment; defaults to 0 if the jq path yields no value
# Usage: append_dot <label> <jq_path> [cap] [mid]
append_dot() {
  local label=$1 jq_path=$2 cap=${3:-100} mid=${4:-50}
  local val
  val=$(echo "$INPUT" | jq -r "${jq_path} // 0")
  PARTS+="${SEP}${label} $(dot "$val" "$cap" "$mid")"
}

# Format Unix epoch as "Xd", "XhYm", or "Xm" remaining
remaining() {
  local reset_epoch=$1
  if [ -z "$reset_epoch" ] || [ "$reset_epoch" = "null" ]; then
    return
  fi
  local now_epoch diff_sec
  now_epoch=$(date "+%s")
  diff_sec=$((reset_epoch - now_epoch))
  if [ "$diff_sec" -le 0 ]; then
    echo "0m"
    return
  fi
  local days=$((diff_sec / 86400))
  local hours=$(( (diff_sec % 86400) / 3600 ))
  local mins=$(( (diff_sec % 3600) / 60 ))
  if [ "$days" -gt 0 ]; then
    echo "${days}d"
  elif [ "$hours" -gt 0 ]; then
    echo "${hours}h${mins}m"
  else
    echo "${mins}m"
  fi
}

# Append a rate-limit dot segment with remaining time as label
# Usage: append_rate <fallback_label> <base_jq_path> [cap]
append_rate() {
  local fallback=$1 base_path=$2 cap=${3:-100}
  local resets_at
  resets_at=$(echo "$INPUT" | jq -r "${base_path}.resets_at // empty")
  local label
  label=$(remaining "$resets_at")
  label=${label:-$fallback}
  local val
  val=$(echo "$INPUT" | jq -r "${base_path}.used_percentage // 0")
  PARTS+="${SEP}${label} $(dot "$val" "$cap")"
}

# ── Components ───────────────────────────────────────────────────

comp_location() {
  local dir
  dir=$(echo "$INPUT" | jq -r '.workspace.current_dir')
  local root
  root=$(git rev-parse --show-toplevel 2>/dev/null) || true
  if [ -n "$root" ]; then
    dir="$root"
  fi
  local now
  now=$(date "+%H:%M:%S")
  local out="${YELLOW}${now}${R}${SEP}${CYAN}${dir##*/}${R}"
  if git rev-parse &>/dev/null; then
    local ref
    ref=$(git branch --show-current)
    if [ -z "$ref" ]; then
      local hash
      hash=$(git rev-parse --short HEAD 2>/dev/null)
      if [ -n "$hash" ]; then
        ref="HEAD ($hash)"
      fi
    fi
    if [ -n "$ref" ]; then
      out+=" on ${MAGENTA}${ICON_BRANCH:+${ICON_BRANCH} }${ref}${R}"
    fi
  fi
  local name
  name=$(echo "$INPUT" | jq -r '.model.display_name')
  out+=" via ${RED}${ICON_MODEL:+${ICON_MODEL} }${name}${R}"
  echo "$out"
}

# ── Main ─────────────────────────────────────────────────────────

INPUT=$(cat)
PARTS="$(comp_location)"

append_dot "ctx" ".context_window.used_percentage" 80 30
append_rate "5h" ".rate_limits.five_hour"
append_rate "7d" ".rate_limits.seven_day"

echo -e "$PARTS"
