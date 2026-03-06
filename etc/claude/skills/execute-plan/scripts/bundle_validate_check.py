#!/usr/bin/env python3
"""Validate plan.md bundle consistency before task execution.

Usage:
  uv run python bundle_validate_check.py plan.md

Checks:
  - ## Checkpoint Summary section exists
  - All 12 required keys are present
  - Alignment Verdict is PASS
  - Trace Pack / Compose Pack values match header links
  - Trace Pack / Compose Pack referenced files exist on disk

Output: LLM_CHECK_V2 format (via shared llm_check helper).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from llm_check import emit_footer, emit_header, emit_line, resolve_mode  # noqa: E402

TOOL_NAME = "bundle-validate-check"

REQUIRED_KEYS = (
    "Alignment Verdict",
    "Forward Fidelity",
    "Reverse Fidelity",
    "Non-Goal Guard",
    "Behavioral Lock Guard",
    "Temporal Completeness Guard",
    "Quality Gate Guard",
    "Integration Coverage Guard",
    "Risk Classification Guard",
    "Trace Pack",
    "Compose Pack",
    "Updated At",
)

# Regex: "- **Key**: value" (list item or plain)
_KV_RE = re.compile(r"^\s*-?\s*\*\*([^*]+)\*\*\s*:\s*(.*)$")


def _extract_section(text: str, title: str) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(title)}\s*$\n(.*?)(?=^##\s|\Z)"
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def _parse_kv(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        m = _KV_RE.match(line)
        if m:
            result[m.group(1).strip()] = m.group(2).strip()
    return result


def _extract_header_links(text: str) -> dict[str, str]:
    """Parse Trace Pack / Compose Pack from plan header (first 40 lines)."""
    result: dict[str, str] = {}
    for line in text.splitlines()[:40]:
        m = _KV_RE.match(line)
        if m:
            key = m.group(1).strip()
            if key in ("Trace Pack", "Compose Pack"):
                result[key] = m.group(2).strip()
    return result


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Bundle consistency validation")
    parser.add_argument("plan_file", help="Path to plan.md")
    args = parser.parse_args(argv[1:])

    mode = resolve_mode()
    plan_path = Path(args.plan_file)

    if not plan_path.exists():
        emit_header(
            TOOL_NAME, mode, "FAIL", "PLAN_FILE_NOT_FOUND",
            f"Plan file not found: {plan_path}",
        )
        emit_line("fix.1", "FIX_PLAN_FILE_PATH")
        emit_footer()
        return 1

    text = plan_path.read_text(encoding="utf-8")
    base_dir = plan_path.parent

    checkpoint_section = _extract_section(text, "Checkpoint Summary")
    if not checkpoint_section:
        emit_header(
            TOOL_NAME, mode, "FAIL", "NO_CHECKPOINT_SUMMARY",
            "No ## Checkpoint Summary section found in plan.md.",
        )
        emit_line("fix.1", "FIX_ADD_CHECKPOINT_SUMMARY_SECTION")
        emit_footer()
        return 1

    kv = _parse_kv(checkpoint_section)
    header_links = _extract_header_links(text)
    issues: list[str] = []

    # 1. Required keys
    missing = [k for k in REQUIRED_KEYS if k not in kv]
    if missing:
        issues.append(f"missing required keys: {', '.join(missing)}")

    # 2. Alignment Verdict must be PASS
    alignment = kv.get("Alignment Verdict", "")
    if alignment != "PASS":
        issues.append(
            f"Alignment Verdict must be exactly PASS, got: {alignment!r}"
        )

    # 3. Trace Pack / Compose Pack must match header links
    for key in ("Trace Pack", "Compose Pack"):
        header_val = header_links.get(key, "").strip()
        summary_val = kv.get(key, "").strip()
        if header_val and summary_val and header_val != summary_val:
            issues.append(
                f"{key}: header={header_val!r} != checkpoint={summary_val!r}"
            )

    # 4. Referenced sidecar files must exist
    for key in ("Trace Pack", "Compose Pack"):
        ref = (kv.get(key) or header_links.get(key) or "").strip()
        if not ref:
            continue
        ref_path = (base_dir / ref) if not Path(ref).is_absolute() else Path(ref)
        if not ref_path.exists():
            issues.append(f"{key} file not found: {ref}")

    overall = "FAIL" if issues else "PASS"
    code = "BUNDLE_VALIDATION_FAILED" if issues else "BUNDLE_VALID"
    summary = (
        f"{len(issues)} bundle validation issue(s) found."
        if issues
        else "Bundle valid: all required keys present, Alignment Verdict PASS, sidecars exist."
    )

    emit_header(TOOL_NAME, mode, overall, code, summary)
    emit_line("signal.checkpoint_keys_found", len(kv))
    emit_line("signal.issues", len(issues))

    for i, issue in enumerate(issues, 1):
        emit_line(f"issue.{i}", issue)

    if issues:
        emit_line("fix.1", "FIX_ADD_MISSING_CHECKPOINT_KEYS")
        emit_line("fix.2", "FIX_SET_ALIGNMENT_VERDICT_PASS")
        emit_line("fix.3", "FIX_RECONCILE_PACK_LINKS_AND_FILES")

    emit_footer()
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
