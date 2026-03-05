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
  echo "FAIL: Source Digest mismatch"
  echo "  Review digest:  $review_digest"
  echo "  Current digest: $current_digest"
  echo "  Source file may have been modified after review"
  exit 1
fi

echo "PASS: All gate checks passed"
exit 0
