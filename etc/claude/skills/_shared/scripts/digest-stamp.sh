#!/usr/bin/env bash
set -euo pipefail

# digest-stamp.sh — Generate review header metadata.
# Usage: digest-stamp.sh <mode> <source-file>
#   mode: design-review | plan-review | dod-recheck | adversarial-verify
#   source-file: path to the artifact being reviewed
# Outputs metadata lines to stdout. Does NOT include Overall Verdict
# (the review skill is responsible for determining and appending that).

if [[ $# -ne 2 ]]; then
  echo "Usage: digest-stamp.sh <mode> <source-file>"
  exit 1
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
  echo "ERROR: Invalid mode '$mode'. Must be one of: ${valid_modes[*]}"
  exit 1
fi

if [[ ! -f "$source_file" ]]; then
  echo "ERROR: Source file not found: $source_file"
  exit 1
fi

abs_path="$(cd "$(dirname "$source_file")" && pwd)/$(basename "$source_file")"
digest=$(shasum -a 256 "$source_file" | cut -d' ' -f1)
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "- **Mode**: $mode"
echo "- **Source Artifact**: $abs_path"
echo "- **Source Digest**: $digest"
echo "- **Reviewed At**: $timestamp"
echo "- **Isolation**: sub-agent (fork_context=false)"
