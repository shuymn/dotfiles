#!/usr/bin/env bash
set -euo pipefail

# gate-check.sh — Verify review gate before downstream skill execution.
# Usage: gate-check.sh <review-file> <source-file>
#   review-file: path to the review artifact (e.g., .../design.review.md)
#   source-file: path to the source artifact that was reviewed
# Performs 5 checks: file existence, overall verdict, source digest, sub-verdicts, exit code verification (dod-recheck only).
# Output:
#   - LLM_CHECK_V2 (default compact mode, minimal token usage)
#   - Set LLM_CHECK_MODE=full for verbose diagnostics
# Exit 0 if all checks pass; exit 1 if any gate fails.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=llm-check-output.sh
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/llm-check-output.sh"
# shellcheck source=path-display.sh
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/path-display.sh"

readonly TOOL_NAME="gate-check"
readonly OUTPUT_SCHEMA="LLM_CHECK_V2"
readonly TOTAL_CHECKS=5

output_mode="$(llm_check_resolve_mode)"
readonly OUTPUT_MODE="$output_mode"

review_file="${1-}"
source_file="${2-}"
display_review_file="$(llm_display_path "$review_file")"
display_source_file="$(llm_display_path "$source_file")"
detail_lines=()
repair_lines=()
compact_fails=()
fix_codes=()

emit_line() {
  llm_check_emit_line "$@"
}

reset_output_context() {
  detail_lines=()
  repair_lines=()
  compact_fails=()
  fix_codes=()
}

add_detail() {
  local key="$1"
  local value="$2"
  detail_lines+=("${key}|${value}")
}

add_repair() {
  local step="$1"
  repair_lines+=("$step")
}

add_compact_fail() {
  local reason="$1"
  compact_fails+=("$reason")
}

add_fix_code() {
  local fix="$1"
  fix_codes+=("$fix")
}

emit_compact_result() {
  local status="$1"
  local code="$2"
  local summary="$3"
  local exit_code="$4"

  local i=0
  local fix=""
  local seen_fixes=()
  local already_seen="false"

  llm_check_emit_header "$OUTPUT_SCHEMA" "$TOOL_NAME" "$OUTPUT_MODE" "$status" "$code" "$summary"

  if [[ "$status" == "PASS" ]]; then
    emit_line "checks.failed" "0"
    llm_check_emit_footer "$OUTPUT_SCHEMA"
    exit "$exit_code"
  fi

  if [[ ${#compact_fails[@]} -eq 0 ]]; then
    compact_fails+=("$summary")
  fi

  emit_line "checks.failed" "${#compact_fails[@]}"
  for i in "${!compact_fails[@]}"; do
    emit_line "fail.$((i + 1))" "${compact_fails[$i]}"
  done

  for fix in "${fix_codes[@]}"; do
    already_seen="false"
    for seen in "${seen_fixes[@]}"; do
      if [[ "$seen" == "$fix" ]]; then
        already_seen="true"
        break
      fi
    done
    if [[ "$already_seen" != "true" ]]; then
      seen_fixes+=("$fix")
    fi
  done

  if [[ ${#seen_fixes[@]} -eq 0 ]]; then
    seen_fixes+=("FIX_RERUN_AFTER_CORRECTION")
  fi

  for i in "${!seen_fixes[@]}"; do
    emit_line "fix.$((i + 1))" "${seen_fixes[$i]}"
  done

  llm_check_emit_footer "$OUTPUT_SCHEMA"
  exit "$exit_code"
}

emit_full_result() {
  local status="$1"
  local code="$2"
  local summary="$3"
  local exit_code="$4"

  local i=0
  local line=""
  local key=""
  local value=""

  llm_check_emit_header "$OUTPUT_SCHEMA" "$TOOL_NAME" "$OUTPUT_MODE" "$status" "$code" "$summary"
  emit_line "checks.total" "$TOTAL_CHECKS"
  emit_line "input.review_file" "$display_review_file"
  emit_line "input.source_file" "$display_source_file"

  for line in "${detail_lines[@]}"; do
    key="${line%%|*}"
    value="${line#*|}"
    emit_line "detail.${key}" "$value"
  done

  if [[ ${#repair_lines[@]} -eq 0 ]]; then
    emit_line "repair.1" "No action required."
  else
    for i in "${!repair_lines[@]}"; do
      emit_line "repair.$((i + 1))" "${repair_lines[$i]}"
    done
  fi

  if [[ "$status" == "PASS" ]]; then
    emit_line "next" "Proceed to downstream skill."
  else
    emit_line "next" "Apply repair steps and rerun this script."
  fi

  llm_check_emit_footer "$OUTPUT_SCHEMA"
  exit "$exit_code"
}

emit_result() {
  local status="$1"
  local code="$2"
  local summary="$3"
  local exit_code="$4"

  if [[ "$OUTPUT_MODE" == "full" ]]; then
    emit_full_result "$status" "$code" "$summary" "$exit_code"
  fi

  emit_compact_result "$status" "$code" "$summary" "$exit_code"
}

join_by() {
  llm_check_join_by "$@"
}

if [[ $# -ne 2 ]]; then
  reset_output_context
  add_compact_fail "arg_count=$#"
  add_fix_code "FIX_USE_TWO_ARGS"
  add_detail "arg_count" "$#"
  add_repair "Run with exactly two arguments: gate-check.sh <review-file> <source-file>."
  add_repair "Pass the reviewed markdown file as <review-file> and its source markdown file as <source-file>."
  emit_result "FAIL" "INVALID_ARGUMENT_COUNT" "Expected exactly 2 arguments." 1
fi

# 1. File existence
if [[ ! -f "$review_file" ]]; then
  reset_output_context
  add_compact_fail "review_file_missing"
  add_fix_code "FIX_REVIEW_FILE_PATH"
  add_detail "missing_path" "$display_review_file"
  add_repair "Confirm <review-file> path exists and is readable."
  add_repair "Use the latest review artifact (e.g., design.review.md or plan.review.md)."
  emit_result "FAIL" "REVIEW_FILE_NOT_FOUND" "Review file was not found." 1
fi

if [[ ! -f "$source_file" ]]; then
  reset_output_context
  add_compact_fail "source_file_missing"
  add_fix_code "FIX_SOURCE_FILE_PATH"
  add_detail "missing_path" "$display_source_file"
  add_repair "Confirm <source-file> path exists and is readable."
  add_repair "Point to the exact source markdown that was reviewed."
  emit_result "FAIL" "SOURCE_FILE_NOT_FOUND" "Source file was not found." 1
fi

# 2. Overall Verdict: PASS (strict)
# Accept both plain and markdown-bold forms, but require EXACT value PASS.
# Rejected examples: "PASS | FAIL", "PASS (tentative)"
verdict_value=$(sed -En 's/^[[:space:]-]*\*{0,2}Overall Verdict\*{0,2}:[[:space:]]*(.*)[[:space:]]*$/\1/p' "$review_file" | head -1 || true)
if [[ -z "$verdict_value" ]]; then
  reset_output_context
  add_compact_fail "overall_verdict_missing"
  add_fix_code "FIX_ADD_OVERALL_VERDICT_LINE"
  add_repair "Add exactly one metadata line: - **Overall Verdict**: PASS or - **Overall Verdict**: FAIL."
  add_repair "Use exact token PASS or FAIL; do not append alternatives or commentary."
  emit_result "FAIL" "MISSING_OVERALL_VERDICT" "Could not find Overall Verdict in review file." 1
fi
if [[ "$verdict_value" != "PASS" && "$verdict_value" != "FAIL" ]]; then
  reset_output_context
  add_compact_fail "overall_verdict_invalid=$verdict_value"
  add_fix_code "FIX_NORMALIZE_OVERALL_VERDICT"
  add_detail "actual_overall_verdict" "$verdict_value"
  add_repair "Normalize Overall Verdict to exactly PASS or FAIL."
  add_repair "Replace values like 'PASS | FAIL' or 'PASS (tentative)' with one exact token."
  emit_result "FAIL" "INVALID_OVERALL_VERDICT_VALUE" "Overall Verdict value is invalid." 1
fi
if [[ "$verdict_value" != "PASS" ]]; then
  reset_output_context
  add_compact_fail "overall_verdict_not_pass=$verdict_value"
  add_fix_code "FIX_RESOLVE_REVIEW_FINDINGS"
  add_fix_code "FIX_REGENERATE_REVIEW"
  add_detail "actual_overall_verdict" "$verdict_value"
  add_repair "Open the review report and inspect failed sections/sub-verdicts."
  add_repair "Fix the underlying issues, regenerate review, and ensure Overall Verdict becomes PASS."
  emit_result "FAIL" "OVERALL_VERDICT_NOT_PASS" "Overall Verdict is FAIL." 1
fi

# 3. Source Digest comparison
# Match both plain "Source Digest: <hash>" and bold "**Source Digest**: <hash>"
review_digest=$(grep -Eo 'Source Digest(\*\*)?:[[:space:]]*[a-f0-9]{64}' "$review_file" 2>/dev/null | sed -E 's/.*:[[:space:]]*//' | head -1 || true)
if [[ -z "$review_digest" ]]; then
  reset_output_context
  add_compact_fail "source_digest_missing"
  add_fix_code "FIX_ADD_SOURCE_DIGEST"
  add_fix_code "FIX_REGENERATE_HEADER"
  add_repair "Add Source Digest to review metadata using a 64-char lowercase SHA-256 hash."
  add_repair "Regenerate metadata with digest-stamp script to avoid manual formatting drift."
  emit_result "FAIL" "MISSING_SOURCE_DIGEST" "Could not extract Source Digest from review file." 1
fi
if [[ ! "$review_digest" =~ ^[a-f0-9]{64}$ ]]; then
  reset_output_context
  add_compact_fail "source_digest_invalid_format"
  add_fix_code "FIX_NORMALIZE_SOURCE_DIGEST"
  add_fix_code "FIX_REGENERATE_HEADER"
  add_detail "actual_source_digest" "$review_digest"
  add_repair "Replace Source Digest with a lowercase 64-character SHA-256 hex string."
  add_repair "Regenerate the review header instead of editing digest manually."
  emit_result "FAIL" "INVALID_SOURCE_DIGEST_FORMAT" "Source Digest format is invalid." 1
fi

current_digest=$(shasum -a 256 "$source_file" | cut -d' ' -f1)
if [[ "$review_digest" != "$current_digest" ]]; then
  reset_output_context
  add_compact_fail "source_digest_mismatch"
  add_fix_code "FIX_RERUN_REVIEW_ON_CURRENT_SOURCE"
  add_fix_code "FIX_UPDATE_SOURCE_DIGEST"
  add_detail "review_digest" "$review_digest"
  add_detail "current_digest" "$current_digest"
  add_repair "Source file changed after review. Re-run review against the current source file."
  add_repair "Update review metadata so Source Digest matches the current source digest."
  emit_result "FAIL" "SOURCE_DIGEST_MISMATCH" "Source Digest does not match current source file." 1
fi

# 4. Sub-verdict verification (when present)
# Extract sub-verdicts from two known formats:
#   List format (decompose-plan review): "- Key: PASS|FAIL|N/A"
#   Table format (design-doc review): "| # | Criterion | Verdict | Evidence |"
fail_count=0
fail_lines=()
sub_count=0

# List format: "- Key: PASS" or "- Key: FAIL" or "- Key: N/A (...)"
while IFS= read -r line; do
  sub_count=$((sub_count + 1))
  verdict=$(echo "$line" | sed -E 's/^- [^:]+:[[:space:]]*//')
  # Check first 3 chars for N/A
  if [[ "${verdict:0:3}" == "N/A" ]]; then
    continue
  fi
  if [[ "$verdict" == "PASS" ]]; then
    continue
  fi
  fail_count=$((fail_count + 1))
  fail_lines+=("$line")
done < <(grep -E '^- [A-Za-z][A-Za-z /()-]*:[[:space:]]*(PASS|FAIL|N/A)' "$review_file" | grep -v '^- \*\{0,2\}Overall Verdict' || true)

# Table format: "| N | Criterion | PASS/FAIL/N/A | Evidence |"
while IFS='|' read -r _ _num _criterion verdict _rest; do
  verdict=$(echo "$verdict" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  # Skip header/separator rows
  if [[ "$verdict" == "Verdict" || "$verdict" == "-"* || -z "$verdict" ]]; then
    continue
  fi
  sub_count=$((sub_count + 1))
  if [[ "${verdict:0:3}" == "N/A" ]]; then
    continue
  fi
  if [[ "$verdict" == "PASS" ]]; then
    continue
  fi
  fail_count=$((fail_count + 1))
  _criterion=$(echo "$_criterion" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  fail_lines+=("${_criterion}: ${verdict}")
done < <(awk '/^## DoD Verification/{skip=1;next} /^## Quality Gate Verification/{skip=1;next} /^## /{skip=0} !skip' "$review_file" | grep -E '^\|[[:space:]]*[0-9]+[[:space:]]*\|.*\|(.*PASS|.*FAIL|.*N/A)' || true)

if [[ $sub_count -gt 0 && $fail_count -gt 0 ]]; then
  reset_output_context
  add_compact_fail "sub_verdict_failures=$fail_count"
  add_fix_code "FIX_RESOLVE_SUB_VERDICTS"
  add_fix_code "FIX_REGENERATE_REVIEW"
  add_detail "sub_verdicts_checked" "$sub_count"
  add_detail "sub_verdicts_failed" "$fail_count"
  add_detail "failed_sub_verdicts" "$(join_by '; ' "${fail_lines[@]}")"
  add_repair "Locate each failed sub-verdict in the review report and resolve the underlying issue."
  add_repair "Regenerate the review report so all sub-verdicts are PASS (N/A allowed when justified)."
  emit_result "FAIL" "SUB_VERDICT_FAILURES" "${fail_count} sub-verdict(s) failed." 1
fi

# 5. Exit code re-verification (dod-recheck reports only)
if grep -q '^## DoD Verification' "$review_file"; then
  nonzero_cmds=()

  # DoD Verification table: | # | Command | Exit Code | Expected | Actual | Verdict |
  dod_section=$(sed -n '/^## DoD Verification/,/^## /p' "$review_file" | sed '$d' || true)
  while IFS='|' read -r _ _num _cmd exit_code _rest; do
    exit_code=$(echo "$exit_code" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    if [[ "$exit_code" =~ ^[0-9]+$ ]] && [[ "$exit_code" != "0" ]]; then
      _cmd=$(echo "$_cmd" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
      nonzero_cmds+=("DoD:${_cmd}:exit=${exit_code}")
    fi
  done < <(echo "$dod_section" | grep -E '^\|[[:space:]]*[0-9]+[[:space:]]*\|' || true)

  # Quality Gate Verification table: | # | Command | Exit Code | Verdict |
  qgate_section=$(sed -n '/^## Quality Gate Verification/,/^## /p' "$review_file" | sed '$d' || true)
  while IFS='|' read -r _ _num _cmd exit_code _rest; do
    exit_code=$(echo "$exit_code" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    if [[ "$exit_code" =~ ^[0-9]+$ ]] && [[ "$exit_code" != "0" ]]; then
      _cmd=$(echo "$_cmd" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
      nonzero_cmds+=("QGate:${_cmd}:exit=${exit_code}")
    fi
  done < <(echo "$qgate_section" | grep -E '^\|[[:space:]]*[0-9]+[[:space:]]*\|' || true)

  if [[ ${#nonzero_cmds[@]} -gt 0 ]]; then
    reset_output_context
    add_compact_fail "nonzero_exit_codes=${#nonzero_cmds[@]}"
    add_fix_code "FIX_RESOLVE_NONZERO_EXIT_CODES"
    add_fix_code "FIX_REGENERATE_REVIEW"
    add_detail "nonzero_count" "${#nonzero_cmds[@]}"
    add_detail "nonzero_details" "$(join_by '; ' "${nonzero_cmds[@]}")"
    add_repair "Fix all DoD/Quality Gate commands to exit with code 0."
    add_repair "Re-run dod-recheck after fixing underlying issues."
    emit_result "FAIL" "NONZERO_EXIT_CODES" "${#nonzero_cmds[@]} command(s) recorded non-zero exit codes." 1
  fi
fi

reset_output_context
add_detail "overall_verdict" "$verdict_value"
add_detail "source_digest" "$review_digest"
add_detail "sub_verdicts_checked" "$sub_count"
emit_result "PASS" "ALL_CHECKS_PASSED" "All gate checks passed." 0
