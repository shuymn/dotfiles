#!/usr/bin/env bash
set -euo pipefail

# digest-stamp.sh — Generate review header metadata.
# Usage: digest-stamp.sh <mode> <source-file>
#   mode: design-review | plan-review | dod-recheck | adversarial-verify
#   source-file: path to the artifact being reviewed
# Outputs metadata lines to stdout. Does NOT include Overall Verdict
# (the review skill is responsible for determining and appending that).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=llm-check-output.sh
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/llm-check-output.sh"

readonly TOOL_NAME="digest-stamp"
readonly OUTPUT_SCHEMA="LLM_CHECK_V2"
output_mode="$(llm_check_resolve_mode)"
readonly OUTPUT_MODE="$output_mode"

emit_error() {
  local code="$1"
  local summary="$2"
  shift 2

  local fix=""

  if [[ "$OUTPUT_MODE" != "full" ]]; then
    llm_check_emit_header "$OUTPUT_SCHEMA" "$TOOL_NAME" "$OUTPUT_MODE" "FAIL" "$code" "$summary"
    llm_check_emit_line "checks.failed" "1"
    llm_check_emit_line "fail.1" "input_error"
    if [[ $# -eq 0 ]]; then
      llm_check_emit_line "fix.1" "FIX_RERUN_AFTER_CORRECTION"
    else
      local idx=1
      for fix in "$@"; do
        llm_check_emit_line "fix.${idx}" "$fix"
        idx=$((idx + 1))
      done
    fi
    llm_check_emit_footer "$OUTPUT_SCHEMA"
    exit 1
  fi

  llm_check_emit_header "$OUTPUT_SCHEMA" "$TOOL_NAME" "$OUTPUT_MODE" "FAIL" "$code" "$summary"
  llm_check_emit_line "input.mode" "${mode-}"
  llm_check_emit_line "input.source_file" "${source_file-}"
  if [[ $# -eq 0 ]]; then
    llm_check_emit_line "repair.1" "Apply correction and rerun digest-stamp.sh."
  else
    local idx=1
    for fix in "$@"; do
      llm_check_emit_line "repair.${idx}" "$fix"
      idx=$((idx + 1))
    done
  fi
  llm_check_emit_line "next" "Apply repair steps and rerun this script."
  llm_check_emit_footer "$OUTPUT_SCHEMA"
  exit 1
}

if [[ $# -ne 2 ]]; then
  emit_error \
    "INVALID_ARGUMENT_COUNT" \
    "Expected exactly 2 arguments." \
    "FIX_USE_TWO_ARGS"
fi

mode="$1"
source_file="$2"

valid_modes=("design-review" "plan-review" "dod-recheck" "adversarial-verify")
mode_valid=false
for m in "${valid_modes[@]}"; do
  if [[ "$mode" == "$m" ]]; then
    mode_valid=true
    break
  fi
done

if [[ "$mode_valid" != "true" ]]; then
  emit_error \
    "INVALID_MODE" \
    "Mode is invalid." \
    "FIX_USE_VALID_MODE"
fi

if [[ ! -f "$source_file" ]]; then
  emit_error \
    "SOURCE_FILE_NOT_FOUND" \
    "Source file was not found." \
    "FIX_SOURCE_FILE_PATH"
fi

abs_path="$(cd "$(dirname "$source_file")" && pwd)/$(basename "$source_file")"
digest=$(shasum -a 256 "$source_file" | cut -d' ' -f1)
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "- **Mode**: $mode"
echo "- **Source Artifact**: $abs_path"
echo "- **Source Digest**: $digest"
echo "- **Reviewed At**: $timestamp"
echo "- **Isolation**: sub-agent (fork_context=false)"
