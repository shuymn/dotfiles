#!/usr/bin/env bash
set -euo pipefail

# structural-check.sh — Structural integrity checks on a plan bundle.
# Usage: structural-check.sh <design-file> <plan-file>
# Performs 4 checks: ID duplicates, dependency cycles, AC coverage, DoD existence.
# Outputs markdown results to stdout.
# Exit 0 if all PASS; exit 1 if any FAIL.

if [[ $# -ne 2 ]]; then
  echo "Usage: structural-check.sh <design-file> <plan-file>"
  exit 1
fi

design_file="$1"
plan_file="$2"

if [[ ! -f "$design_file" ]]; then
  echo "ERROR: Design file not found: $design_file"
  exit 1
fi

if [[ ! -f "$plan_file" ]]; then
  echo "ERROR: Plan file not found: $plan_file"
  exit 1
fi

has_failure=false

echo "## Structural Check Results"
echo ""

# --- Check 1: Task ID duplicates ---
echo "### 1. Task ID Uniqueness"
duplicates=$(grep -oE '### Task [0-9]+' "$plan_file" | sort | uniq -d || true)
if [[ -z "$duplicates" ]]; then
  echo "- **Verdict**: PASS"
  echo "- No duplicate task IDs found."
else
  echo "- **Verdict**: FAIL"
  echo "- Duplicate task IDs:"
  echo "$duplicates" | while read -r line; do echo "  - $line"; done
  has_failure=true
fi
echo ""

# --- Check 2: Dependency cycle detection ---
echo "### 2. Dependency Cycle Detection"
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
done < "$plan_file" > "$edges_file"

if [[ ! -s "$edges_file" ]]; then
  echo "- **Verdict**: PASS"
  echo "- No dependencies found (or all tasks are independent)."
else
  # Note: On some platforms (e.g., macOS), tsort may emit cycle errors but still exit 0.
  # Treat any "tsort:" diagnostic output as FAIL.
  tsort_output=$(tsort "$edges_file" 2>&1 || true)
  if echo "$tsort_output" | grep -q '^tsort:'; then
    echo "- **Verdict**: FAIL"
    echo "- Dependency graph validation failed:"
    echo "  \`\`\`"
    echo "  $tsort_output"
    echo "  \`\`\`"
    has_failure=true
  else
    echo "- **Verdict**: PASS"
    echo "- No dependency cycles detected."
  fi
fi
echo ""

# --- Check 3: AC coverage ---
echo "### 3. AC Coverage (Design -> Plan)"
# Extract AC IDs from design
design_acs=$(grep -oE 'AC[A-Za-z0-9_-]*[0-9]+' "$design_file" | sort -u || true)
# Extract AC references from plan
plan_acs=$(grep -oE 'AC[A-Za-z0-9_-]*[0-9]+' "$plan_file" | sort -u || true)

if [[ -z "$design_acs" ]]; then
  echo "- **Verdict**: PASS"
  echo "- No AC IDs found in design (non-standard format or no ACs defined)."
else
  missing_acs=$(comm -23 <(echo "$design_acs") <(echo "$plan_acs") || true)
  if [[ -z "$missing_acs" ]]; then
    echo "- **Verdict**: PASS"
    echo "- All design ACs are referenced in the plan."
  else
    echo "- **Verdict**: FAIL"
    echo "- ACs in design but not referenced in plan:"
    echo "$missing_acs" | while read -r ac; do echo "  - $ac"; done
    has_failure=true
  fi
fi
echo ""

# --- Check 4: DoD existence per task ---
echo "### 4. DoD Existence"
tasks_without_dod=""
while IFS= read -r task_header; do
  task_id=$(echo "$task_header" | grep -oE 'Task [0-9]+')
  task_num=$(echo "$task_id" | grep -oE '[0-9]+')
  # Check if DoD exists between this task header and the next task header (or EOF)
  task_section=$(sed -n "/^### Task ${task_num}[^0-9]/,/^### Task [0-9]/p" "$plan_file" | sed '$d')
  if [[ -z "$task_section" ]]; then
    # Last task — read to EOF
    task_section=$(sed -n "/^### Task ${task_num}[^0-9]/,\$p" "$plan_file")
  fi
  if ! echo "$task_section" | grep -q '\*\*DoD\*\*'; then
    tasks_without_dod="${tasks_without_dod}  - Task ${task_num}\n"
  fi
done < <(grep -E '^### Task [0-9]+' "$plan_file")

if [[ -z "$tasks_without_dod" ]]; then
  echo "- **Verdict**: PASS"
  echo "- All tasks have DoD defined."
else
  echo "- **Verdict**: FAIL"
  echo "- Tasks missing **DoD**:"
  printf '%b' "$tasks_without_dod"
  has_failure=true
fi
echo ""

# --- Final verdict ---
echo "---"
if [[ "$has_failure" == "true" ]]; then
  echo "**Overall Structural Check: FAIL**"
  exit 1
else
  echo "**Overall Structural Check: PASS**"
  exit 0
fi
