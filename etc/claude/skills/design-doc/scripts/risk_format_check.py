#!/usr/bin/env python3
"""Check Risk Classification section format in a design doc.

Usage:
  uv run --with pydantic python risk_format_check.py design.md

Checks (structural/format only — semantic justification quality is LLM's job):
  - ## Risk Classification section exists (SKIP if absent for greenfield)
  - At least one table row exists
  - Critical/Sensitive rows: change_rationale matches
      "Defect Impact: [...] / Blast Radius: [...]"
  - Standard rows: change_rationale matches
      "Not Critical: [...] / Not Sensitive: [...]"

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

TOOL_NAME = "risk-format-check"

# Rationale format patterns (anchored to the presence of required keywords)
_CS_RE = re.compile(r"Defect Impact\s*:.+?/\s*Blast Radius\s*:", re.IGNORECASE | re.DOTALL)
_STD_RE = re.compile(r"Not Critical\s*:.+?/\s*Not Sensitive\s*:", re.IGNORECASE | re.DOTALL)


def _extract_section(text: str, title: str) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(title)}\s*$\n(.*?)(?=^##\s|\Z)"
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def _parse_table(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return rows
    headers = [h.strip() for h in lines[0].strip("|").split("|")]
    sep_cells = [c.strip() for c in lines[1].strip("|").split("|")]
    if not all(re.fullmatch(r":?-{2,}:?", c or "-") for c in sep_cells):
        return rows
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def check_risk_row(row: dict[str, str]) -> tuple[bool, str]:
    """Return (ok, issue). Checks format only, not semantic quality."""
    tier = (row.get("Risk Tier") or row.get("risk_tier") or "").strip()
    rationale = (row.get("Change Rationale") or row.get("change_rationale") or "").strip()
    area = (row.get("Area") or row.get("area") or "?").strip()

    if tier in ("Critical", "Sensitive"):
        if not _CS_RE.search(rationale):
            return (
                False,
                f"{area} ({tier}): Change Rationale must contain"
                " 'Defect Impact: [...] / Blast Radius: [...]'",
            )
    elif tier == "Standard":
        if not _STD_RE.search(rationale):
            return (
                False,
                f"{area} (Standard): Change Rationale must contain"
                " 'Not Critical: [...] / Not Sensitive: [...]'",
            )
    # Unknown or empty tier: skip (LLM validates tier validity)
    return (True, "")


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Risk Classification format check"
    )
    parser.add_argument("design_file", help="Path to design.md")
    args = parser.parse_args(argv[1:])

    mode = resolve_mode()
    design_path = Path(args.design_file)

    if not design_path.exists():
        emit_header(
            TOOL_NAME, mode, "FAIL", "DESIGN_FILE_NOT_FOUND",
            f"Design file not found: {design_path}",
        )
        emit_line("fix.1", "FIX_DESIGN_FILE_PATH")
        emit_footer()
        return 1

    text = design_path.read_text(encoding="utf-8")
    section = _extract_section(text, "Risk Classification")

    if not section:
        emit_header(
            TOOL_NAME, mode, "SKIP", "NO_RISK_CLASSIFICATION_SECTION",
            "No ## Risk Classification section found."
            " Section is optional for greenfield designs without Critical domains.",
        )
        emit_footer()
        return 0

    rows = _parse_table(section)

    if not rows:
        emit_header(
            TOOL_NAME, mode, "FAIL", "RISK_TABLE_EMPTY",
            "## Risk Classification section exists but has no table rows.",
        )
        emit_line("fix.1", "FIX_ADD_RISK_TABLE_ROWS")
        emit_footer()
        return 1

    failures: list[str] = []
    for row in rows:
        ok, issue = check_risk_row(row)
        if not ok:
            failures.append(issue)

    overall = "FAIL" if failures else "PASS"
    code = "RISK_FORMAT_VIOLATIONS" if failures else "ALL_RISK_ROWS_VALID"
    summary = (
        f"{len(failures)} risk row(s) have format violations."
        if failures
        else f"All {len(rows)} risk row(s) have valid Change Rationale format."
    )

    emit_header(TOOL_NAME, mode, overall, code, summary)
    emit_line("signal.total_rows", len(rows))
    emit_line("signal.failures", len(failures))

    for i, issue in enumerate(failures, 1):
        emit_line(f"fail.{i}", issue)

    if failures:
        emit_line(
            "fix.1",
            "FIX_CRITICAL_SENSITIVE: use 'Defect Impact: [...] / Blast Radius: [...]'",
        )
        emit_line(
            "fix.2",
            "FIX_STANDARD: use 'Not Critical: [...] / Not Sensitive: [...]'",
        )

    emit_footer()
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
