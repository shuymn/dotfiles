#!/usr/bin/env bash
set -euo pipefail

# structural-check.sh — Structural integrity checks on a plan bundle.
# Usage: structural-check.sh <design-file> <plan-file>
# Performs 5 checks: ID duplicates, dependency cycles, AC coverage, DoD existence, Quality Gate executability.
# Output:
#   - LLM_CHECK_V2 (default compact mode, minimal token usage)
#   - Set LLM_CHECK_MODE=full for verbose diagnostics
# Exit 0 if all PASS; exit 1 if any FAIL.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../_shared/scripts/llm-check-output.sh
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/../../_shared/scripts/llm-check-output.sh"

readonly TOOL_NAME="structural-check"
readonly OUTPUT_SCHEMA="LLM_CHECK_V2"
readonly TOTAL_CHECKS=5
readonly LIST_DELIMITER=$'\x1f'

output_mode="$(llm_check_resolve_mode)"
readonly OUTPUT_MODE="$output_mode"

design_file="${1-}"
plan_file="${2-}"

check_ids=()
check_statuses=()
check_summaries=()
check_evidences=()
check_repairs=()

emit_line() {
  llm_check_emit_line "$@"
}

join_by() {
  llm_check_join_by "$@"
}

compact_evidence() {
  local evidence="${1-}"
  evidence=$(llm_check_sanitize_value "$evidence")
  evidence=$(echo "$evidence" | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')
  if [[ ${#evidence} -gt 80 ]]; then
    evidence="${evidence:0:80}..."
  fi
  printf '%s' "$evidence"
}

fix_code_for_check() {
  local check_id="$1"
  case "$check_id" in
  "ID-Uniqueness")
    printf '%s' "FIX_RENUMBER_TASK_IDS"
    ;;
  "Dep-Cycle")
    printf '%s' "FIX_BREAK_DEPENDENCY_CYCLE"
    ;;
  "AC-Coverage")
    printf '%s' "FIX_ADD_MISSING_AC_REFERENCES"
    ;;
  "DoD-Existence")
    printf '%s' "FIX_ADD_MISSING_DOD"
    ;;
  "QGate-Exec")
    printf '%s' "FIX_INSTALL_OR_UPDATE_QGATE_COMMANDS"
    ;;
  *)
    printf '%s' "FIX_RERUN_AFTER_CORRECTION"
    ;;
  esac
}

fix_code_for_early_error() {
  local error_code="$1"
  case "$error_code" in
  "INVALID_ARGUMENT_COUNT")
    printf '%s' "FIX_USE_TWO_ARGS"
    ;;
  "DESIGN_FILE_NOT_FOUND")
    printf '%s' "FIX_DESIGN_FILE_PATH"
    ;;
  "PLAN_FILE_NOT_FOUND")
    printf '%s' "FIX_PLAN_FILE_PATH"
    ;;
  *)
    printf '%s' "FIX_RERUN_AFTER_CORRECTION"
    ;;
  esac
}

append_check() {
  local id="$1"
  local status="$2"
  local summary="$3"
  local evidence="$4"
  shift 4

  local repairs_joined=""
  local repair=""
  for repair in "$@"; do
    if [[ -z "$repairs_joined" ]]; then
      repairs_joined="$repair"
    else
      repairs_joined+="${LIST_DELIMITER}${repair}"
    fi
  done

  check_ids+=("$id")
  check_statuses+=("$status")
  check_summaries+=("$summary")
  check_evidences+=("$evidence")
  check_repairs+=("$repairs_joined")
}

emit_early_fail() {
  local code="$1"
  local summary="$2"
  shift 2

  if [[ "$OUTPUT_MODE" != "full" ]]; then
    llm_check_emit_header "$OUTPUT_SCHEMA" "$TOOL_NAME" "$OUTPUT_MODE" "FAIL" "$code" "$summary"
    emit_line "checks.failed" "1"
    emit_line "fail.1" "input_error"
    emit_line "fix.1" "$(fix_code_for_early_error "$code")"
    llm_check_emit_footer "$OUTPUT_SCHEMA"
    exit 1
  fi

  llm_check_emit_header "$OUTPUT_SCHEMA" "$TOOL_NAME" "$OUTPUT_MODE" "FAIL" "$code" "$summary"
  emit_line "checks.total" "$TOTAL_CHECKS"
  emit_line "checks.completed" "0"
  emit_line "input.design_file" "$design_file"
  emit_line "input.plan_file" "$plan_file"
  local idx=1
  local step=""
  for step in "$@"; do
    emit_line "repair.${idx}" "$step"
    idx=$((idx + 1))
  done
  emit_line "next" "Apply repair steps and rerun this script."
  llm_check_emit_footer "$OUTPUT_SCHEMA"
  exit 1
}

emit_result() {
  local status="$1"
  local code="$2"
  local summary="$3"
  local exit_code="$4"

  local i=0
  local j=0
  local failed_count=0
  local failed_ids=()
  local repairs_text=""
  local repairs=()

  if [[ "$OUTPUT_MODE" != "full" ]]; then
    llm_check_emit_header "$OUTPUT_SCHEMA" "$TOOL_NAME" "$OUTPUT_MODE" "$status" "$code" "$summary"

    if [[ "$status" == "PASS" ]]; then
      emit_line "checks.failed" "0"
      llm_check_emit_footer "$OUTPUT_SCHEMA"
      exit "$exit_code"
    fi

    for i in "${!check_ids[@]}"; do
      if [[ "${check_statuses[$i]}" == "FAIL" ]]; then
        failed_count=$((failed_count + 1))
      fi
    done
    emit_line "checks.failed" "$failed_count"

    local fail_idx=1
    local check_id=""
    local check_fix=""
    local check_evidence=""
    for i in "${!check_ids[@]}"; do
      if [[ "${check_statuses[$i]}" != "FAIL" ]]; then
        continue
      fi
      check_id="${check_ids[$i]}"
      check_fix="$(fix_code_for_check "$check_id")"
      check_evidence="$(compact_evidence "${check_evidences[$i]}")"
      if [[ -n "$check_evidence" ]]; then
        emit_line "fail.${fail_idx}" "${check_id}|e=${check_evidence}|fix=${check_fix}"
      else
        emit_line "fail.${fail_idx}" "${check_id}|fix=${check_fix}"
      fi
      fail_idx=$((fail_idx + 1))
    done
    emit_line "fix.1" "FIX_APPLY_FAIL_FIX_CODES"
    emit_line "fix.2" "FIX_RERUN_STRUCTURAL_CHECK"
    llm_check_emit_footer "$OUTPUT_SCHEMA"
    exit "$exit_code"
  fi

  llm_check_emit_header "$OUTPUT_SCHEMA" "$TOOL_NAME" "$OUTPUT_MODE" "$status" "$code" "$summary"
  emit_line "checks.total" "$TOTAL_CHECKS"
  emit_line "checks.completed" "${#check_ids[@]}"
  emit_line "input.design_file" "$design_file"
  emit_line "input.plan_file" "$plan_file"

  for i in "${!check_ids[@]}"; do
    emit_line "check.$((i + 1)).id" "${check_ids[$i]}"
    emit_line "check.$((i + 1)).status" "${check_statuses[$i]}"
    emit_line "check.$((i + 1)).summary" "${check_summaries[$i]}"
    if [[ -n "${check_evidences[$i]}" ]]; then
      emit_line "check.$((i + 1)).evidence" "${check_evidences[$i]}"
    fi

    repairs_text="${check_repairs[$i]}"
    if [[ -n "$repairs_text" ]]; then
      IFS="$LIST_DELIMITER" read -r -a repairs <<<"$repairs_text"
      for j in "${!repairs[@]}"; do
        emit_line "check.$((i + 1)).repair.$((j + 1))" "${repairs[$j]}"
      done
    fi

    if [[ "${check_statuses[$i]}" == "FAIL" ]]; then
      failed_count=$((failed_count + 1))
      failed_ids+=("${check_ids[$i]}")
    fi
  done

  emit_line "checks.failed" "$failed_count"
  emit_line "checks.failed_ids" "$(join_by ',' "${failed_ids[@]}")"

  if [[ "$status" == "PASS" ]]; then
    emit_line "repair.1" "No action required."
    emit_line "next" "Proceed to plan review output."
  else
    emit_line "repair.1" "Fix all checks where check.<n>.status=FAIL."
    emit_line "repair.2" "Re-run structural-check.sh <design-file> <plan-file> until checks.failed=0."
    emit_line "next" "Apply repair steps and rerun this script."
  fi

  llm_check_emit_footer "$OUTPUT_SCHEMA"
  exit "$exit_code"
}

if [[ $# -ne 2 ]]; then
  emit_early_fail \
    "INVALID_ARGUMENT_COUNT" \
    "Expected exactly 2 arguments." \
    "Run with: structural-check.sh <design-file> <plan-file>." \
    "Provide existing markdown files for both inputs."
fi

if [[ ! -f "$design_file" ]]; then
  emit_early_fail \
    "DESIGN_FILE_NOT_FOUND" \
    "Design file was not found." \
    "Confirm <design-file> path exists and is readable." \
    "Pass the same design markdown used for plan decomposition."
fi

if [[ ! -f "$plan_file" ]]; then
  emit_early_fail \
    "PLAN_FILE_NOT_FOUND" \
    "Plan file was not found." \
    "Confirm <plan-file> path exists and is readable." \
    "Generate or locate plan.md before running this check."
fi

# --- Check 1: Task ID duplicates ---
duplicates=$(grep -oE '### Task [0-9]+' "$plan_file" | sort | uniq -d || true)
if [[ -z "$duplicates" ]]; then
  append_check "ID-Uniqueness" "PASS" "No duplicate task IDs found." ""
else
  duplicate_items=()
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    duplicate_items+=("$line")
  done <<<"$duplicates"

  append_check \
    "ID-Uniqueness" \
    "FAIL" \
    "Duplicate task IDs found." \
    "$(join_by '; ' "${duplicate_items[@]}")" \
    "Ensure each '### Task N' header has a unique integer N." \
    "Renumber duplicate tasks and update all related T<N> dependency references."
fi

# --- Check 2: Dependency cycle detection ---
# Extract edges: Task N depends on T1, T2 -> "1 N", "2 N"
edges_file=$(mktemp)
trap 'rm -f "$edges_file"' EXIT

# Build edges from plan file by parsing task blocks
current_task=""
while IFS= read -r line; do
  if [[ "$line" =~ ^###\ Task\ ([0-9]+) ]]; then
    current_task="${BASH_REMATCH[1]}"
  elif [[ -n "$current_task" ]] && { [[ "$line" =~ ^\*\*Dependencies\*\*:\ *(.*) ]] || [[ "$line" =~ ^-\ \*\*Dependencies\*\*:\ *(.*) ]]; }; then
    deps_str="${BASH_REMATCH[1]}"
    if [[ "$deps_str" != "none" ]] && [[ "$deps_str" != "None" ]] && [[ -n "$deps_str" ]]; then
      # Parse comma-separated T<N> references
      echo "$deps_str" | grep -oE 'T[0-9]+' | while read -r dep; do
        dep_num="${dep#T}"
        echo "$dep_num $current_task"
      done
    fi
  fi
done <"$plan_file" >"$edges_file"

if [[ ! -s "$edges_file" ]]; then
  append_check "Dep-Cycle" "PASS" "No dependencies found or all tasks are independent." ""
else
  # Note: On some platforms (e.g., macOS), tsort may emit cycle errors but still exit 0.
  # Treat any "tsort:" diagnostic output as FAIL.
  tsort_output=$(tsort "$edges_file" 2>&1 || true)
  if echo "$tsort_output" | grep -q '^tsort:'; then
    append_check \
      "Dep-Cycle" \
      "FAIL" \
      "Dependency graph contains cycle(s) or invalid edges." \
      "$tsort_output" \
      "Make dependency graph acyclic by removing circular task dependencies." \
      "If a dependency is optional, remove it from **Dependencies** and document rationale in task notes."
  else
    append_check "Dep-Cycle" "PASS" "No dependency cycles detected." ""
  fi
fi

# --- Check 3: AC coverage ---
# Extract AC IDs from design
design_acs=$(grep -oE 'AC[A-Za-z0-9_-]*[0-9]+' "$design_file" | sort -u || true)
# Extract AC references from plan
plan_acs=$(grep -oE 'AC[A-Za-z0-9_-]*[0-9]+' "$plan_file" | sort -u || true)

if [[ -z "$design_acs" ]]; then
  append_check "AC-Coverage" "PASS" "No AC IDs found in design." ""
else
  missing_acs=$(comm -23 <(echo "$design_acs") <(echo "$plan_acs") || true)
  if [[ -z "$missing_acs" ]]; then
    append_check "AC-Coverage" "PASS" "All design ACs are referenced in the plan." ""
  else
    missing_ac_items=()
    while IFS= read -r ac; do
      [[ -z "$ac" ]] && continue
      missing_ac_items+=("$ac")
    done <<<"$missing_acs"

    append_check \
      "AC-Coverage" \
      "FAIL" \
      "Some design ACs are missing from plan references." \
      "$(join_by '; ' "${missing_ac_items[@]}")" \
      "Add missing AC references to task-level Satisfied Requirements and Design Anchors." \
      "Ensure each missing AC is owned by exactly one owner task."
  fi
fi

# --- Check 4: DoD existence per task ---
tasks_without_dod=()
current_task=""
current_task_has_dod="false"
while IFS= read -r line || [[ -n "$line" ]]; do
  if [[ "$line" =~ ^###\ Task\ ([0-9]+) ]]; then
    if [[ -n "$current_task" && "$current_task_has_dod" != "true" ]]; then
      tasks_without_dod+=("Task ${current_task}")
    fi
    current_task="${BASH_REMATCH[1]}"
    current_task_has_dod="false"
    continue
  fi

  if [[ -n "$current_task" && "$line" == *"**DoD**"* ]]; then
    current_task_has_dod="true"
  fi
done <"$plan_file"

if [[ -n "$current_task" && "$current_task_has_dod" != "true" ]]; then
  tasks_without_dod+=("Task ${current_task}")
fi

if [[ ${#tasks_without_dod[@]} -eq 0 ]]; then
  append_check "DoD-Existence" "PASS" "All tasks have DoD defined." ""
else
  append_check \
    "DoD-Existence" \
    "FAIL" \
    "Some tasks are missing DoD sections." \
    "$(join_by '; ' "${tasks_without_dod[@]}")" \
    "Add a **DoD** section to every task block." \
    "Ensure DoD items are executable and verifiable commands or checks."
fi

# --- Check 5: Quality Gate Executability ---
# Extract commands from ## Quality Gates table in plan file
quality_gates_section=$(sed -n '/^## Quality Gates/,/^## /p' "$plan_file" | sed '$d' || true)
if [[ -z "$quality_gates_section" ]]; then
  append_check "QGate-Exec" "PASS" "No Quality Gates section found." ""
else
  missing_cmds=()
  # Extract first backtick-wrapped command from each data row.
  # This avoids brittle hardcoding of pipe column positions.
  while IFS= read -r row; do
    cmd=$(echo "$row" | grep -oE "\`[^\`]+\`" | head -n 1 | tr -d '`' || true)
    first_token=$(echo "$cmd" | awk '{print $1}')
    if [[ -n "$first_token" ]] && ! command -v "$first_token" >/dev/null 2>&1; then
      missing_cmds+=("$first_token")
    fi
  done < <(echo "$quality_gates_section" | grep '^|' | grep -v '^|[[:space:]]*-' | tail -n +2 || true)

  if [[ ${#missing_cmds[@]} -eq 0 ]]; then
    append_check "QGate-Exec" "PASS" "All Quality Gate commands are executable." ""
  else
    append_check \
      "QGate-Exec" \
      "FAIL" \
      "Some Quality Gate commands are not executable in current environment." \
      "$(join_by '; ' "${missing_cmds[@]}")" \
      "Install missing commands or replace them with available executables." \
      "Update Quality Gates table commands so the first token resolves via command -v."
  fi
fi

# --- Final verdict ---
failed_count=0
for status in "${check_statuses[@]}"; do
  if [[ "$status" == "FAIL" ]]; then
    failed_count=$((failed_count + 1))
  fi
done

if [[ "$failed_count" -gt 0 ]]; then
  emit_result \
    "FAIL" \
    "STRUCTURAL_CHECK_FAILED" \
    "${failed_count} of ${TOTAL_CHECKS} structural checks failed." \
    1
else
  emit_result \
    "PASS" \
    "ALL_CHECKS_PASSED" \
    "All ${TOTAL_CHECKS} structural checks passed." \
    0
fi
