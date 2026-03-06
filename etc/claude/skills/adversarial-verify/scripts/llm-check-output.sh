#!/usr/bin/env bash

# Shared helpers for LLM_CHECK_* output contracts.

llm_check_resolve_mode() {
  local mode="${LLM_CHECK_MODE:-compact}"
  if [[ "$mode" != "compact" && "$mode" != "full" ]]; then
    mode="compact"
  fi
  printf '%s' "$mode"
}

llm_check_sanitize_value() {
  local value="${1-}"
  value="${value//$'\r'/}"
  value="${value//$'\n'/\\n}"
  printf '%s' "$value"
}

llm_check_emit_line() {
  local key="$1"
  local value="${2-}"
  printf '%s=%s\n' "$key" "$(llm_check_sanitize_value "$value")"
}

llm_check_emit_header() {
  local schema="$1"
  local tool="$2"
  local mode="$3"
  local status="$4"
  local code="$5"
  local summary="$6"
  echo "$schema"
  llm_check_emit_line "tool" "$tool"
  llm_check_emit_line "mode" "$mode"
  llm_check_emit_line "status" "$status"
  llm_check_emit_line "code" "$code"
  llm_check_emit_line "summary" "$summary"
}

llm_check_emit_footer() {
  local schema="$1"
  echo "END_${schema}"
}

llm_check_join_by() {
  local delimiter="$1"
  shift
  if [[ $# -eq 0 ]]; then
    printf ''
    return
  fi
  local result="$1"
  shift
  local part=""
  for part in "$@"; do
    result+="${delimiter}${part}"
  done
  printf '%s' "$result"
}
