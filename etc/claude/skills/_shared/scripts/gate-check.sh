#!/usr/bin/env bash
set -euo pipefail

# gate-check.sh — Verify review gate before downstream skill execution.
# Usage: gate-check.sh <review-file> <source-file>
#   review-file: path to the review artifact (e.g., .../design.review.md)
#   source-file: path to the source artifact that was reviewed
# Exit 0 if all checks pass; exit 1 with reason on stdout otherwise.

if [[ $# -ne 2 ]]; then
  echo "Usage: gate-check.sh <review-file> <source-file>"
  exit 1
fi

review_file="$1"
source_file="$2"

# 1. File existence
if [[ ! -f "$review_file" ]]; then
  echo "FAIL: Review file not found: $review_file"
  exit 1
fi

if [[ ! -f "$source_file" ]]; then
  echo "FAIL: Source file not found: $source_file"
  exit 1
fi

# 2. Overall Verdict: PASS (strict)
# Accept both plain and markdown-bold forms, but require EXACT value PASS.
# Rejected examples: "PASS | FAIL", "PASS (tentative)"
verdict_value=$(sed -En 's/^[[:space:]-]*\*{0,2}Overall Verdict\*{0,2}:[[:space:]]*(.*)[[:space:]]*$/\1/p' "$review_file" | head -1 || true)
if [[ -z "$verdict_value" ]]; then
  echo "FAIL: Could not find Overall Verdict in review file"
  exit 1
fi
if [[ "$verdict_value" != "PASS" && "$verdict_value" != "FAIL" ]]; then
  echo "FAIL: Overall Verdict has invalid value: '$verdict_value' (expected: PASS or FAIL)"
  exit 1
fi
if [[ "$verdict_value" != "PASS" ]]; then
  echo "FAIL: Overall Verdict is not PASS (found: $verdict_value)"
  exit 1
fi

# 3. Source Digest comparison
# Match both plain "Source Digest: <hash>" and bold "**Source Digest**: <hash>"
review_digest=$(grep -Eo 'Source Digest(\*\*)?:[[:space:]]*[a-f0-9]{64}' "$review_file" 2>/dev/null | sed -E 's/.*:[[:space:]]*//' | head -1 || true)
if [[ -z "$review_digest" ]]; then
  echo "FAIL: Could not extract Source Digest from review file"
  exit 1
fi
if [[ ! "$review_digest" =~ ^[a-f0-9]{64}$ ]]; then
  echo "FAIL: Source Digest has invalid format: '$review_digest' (expected: 64-character hex string)"
  exit 1
fi

current_digest=$(shasum -a 256 "$source_file" | cut -d' ' -f1)
if [[ "$review_digest" != "$current_digest" ]]; then
  echo "FAIL: Source Digest mismatch — source file may have been modified after review"
  echo "  Review digest:  $review_digest" >&2
  echo "  Current digest: $current_digest" >&2
  exit 1
fi

# 4. Sub-verdict verification (when present)
# Extract sub-verdicts from two known formats:
#   List format (decompose-plan review): "- Key: PASS|FAIL|N/A"
#   Table format (design-doc review): "| # | Criterion | Verdict | Evidence |"
fail_count=0
fail_lines=""
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
  fail_lines="${fail_lines}  ${line}"$'\n'
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
  fail_lines="${fail_lines}  ${_criterion}: ${verdict}"$'\n'
done < <(grep -E '^\|[[:space:]]*[0-9]+[[:space:]]*\|.*\|(.*PASS|.*FAIL|.*N/A)' "$review_file" || true)

if [[ $sub_count -gt 0 && $fail_count -gt 0 ]]; then
  echo "FAIL: ${fail_count} sub-verdict(s) failed:"
  printf '%s' "$fail_lines"
  exit 1
fi

echo "PASS: All gate checks passed"
exit 0
