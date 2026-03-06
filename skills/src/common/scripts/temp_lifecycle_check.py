#!/usr/bin/env python3
"""Check TEMPxx lifecycle structure completeness in a design doc.

Usage:
  uv run --with pydantic python temp_lifecycle_check.py design.md [--base-dir <repo-root>]

Checks (when ## Compatibility & Sunset exists):
  - Every TEMPxx in Temporary Mechanism Index has a matching Sunset Closure Checklist row
  - Every TEMPxx in Sunset Closure Checklist has a matching Index entry
  - Checklist rows have non-empty: Retirement Trigger, Retirement Verification, Removal Scope
  - If lifecycle_record references an ADR path (docs/adr/.../*.md), the file exists

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

TOOL_NAME = "temp-lifecycle-check"
TEMP_ID_RE = re.compile(r"\bTEMP[A-Za-z0-9_-]*[0-9]+\b")
ADR_PATH_RE = re.compile(r"docs/adr/[^\s)\]>]+\.md")
NONE_TOKENS = {"", "-", "none", "n/a", "na", "tbd", "tbd-at-plan"}

# Column name variants for each required field
_ID_COLS = ("ID", "id", "Temp ID", "TEMP ID", "TempID")
_MECHANISM_COLS = ("Mechanism", "mechanism")
_LIFECYCLE_COLS = ("Lifecycle Record", "lifecycle_record", "Lifecycle", "ADR/Ledger")
_STATUS_COLS = ("Status", "status")
_TRIGGER_COLS = ("Retirement Trigger", "retirement_trigger", "Trigger")
_VERIFICATION_COLS = ("Retirement Verification", "retirement_verification", "Verification")
_SCOPE_COLS = ("Removal Scope", "removal_scope", "Scope")


def _extract_section(text: str, title: str) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(title)}\s*$\n(.*?)(?=^##\s|\Z)"
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def _extract_subsection(text: str, title: str) -> str:
    """Extract ### or #### subsection within a parent section."""
    pattern = re.compile(
        rf"(?ms)^###{{1,2}}\s+{re.escape(title)}\s*$\n(.*?)(?=^##{{1,3}}\s|\Z)"
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


def _get_col(row: dict[str, str], variants: tuple[str, ...]) -> str:
    for col in variants:
        val = row.get(col, "")
        if val:
            return val.strip()
    return ""


def _extract_temp_rows(section_text: str, id_cols: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """Parse table in section; return {temp_id: row} for rows with TEMP IDs."""
    result: dict[str, dict[str, str]] = {}
    rows = _parse_table(section_text)
    for row in rows:
        id_val = _get_col(row, id_cols)
        ids = TEMP_ID_RE.findall(id_val)
        if ids:
            result[ids[0]] = row
    return result


def _find_compat_section(text: str) -> str:
    for title in ("Compatibility & Sunset", "Compatibility and Sunset", "Compatibility"):
        section = _extract_section(text, title)
        if section:
            return section
    return ""


def _find_index_section(compat: str) -> str:
    for title in ("Temporary Mechanism Index", "Temporary Mechanism Ledger"):
        sub = _extract_subsection(compat, title)
        if sub:
            return sub
    return ""


def _find_checklist_section(compat: str) -> str:
    for title in ("Sunset Closure Checklist",):
        sub = _extract_subsection(compat, title)
        if sub:
            return sub
    return ""


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="TEMPxx lifecycle structure check")
    parser.add_argument("design_file", help="Path to design.md")
    parser.add_argument(
        "--base-dir",
        default="",
        help="Base directory for ADR file resolution (default: design file's directory)",
    )
    args = parser.parse_args(argv[1:])

    mode = resolve_mode()
    design_path = Path(args.design_file)
    base_dir = Path(args.base_dir) if args.base_dir else design_path.parent

    if not design_path.exists():
        emit_header(
            TOOL_NAME, mode, "FAIL", "DESIGN_FILE_NOT_FOUND",
            f"Design file not found: {design_path}",
        )
        emit_line("fix.1", "FIX_DESIGN_FILE_PATH")
        emit_footer()
        return 1

    text = design_path.read_text(encoding="utf-8")
    compat = _find_compat_section(text)

    if not compat:
        emit_header(
            TOOL_NAME, mode, "SKIP", "NO_COMPATIBILITY_SUNSET_SECTION",
            "No ## Compatibility & Sunset section found. TEMPxx lifecycle check skipped.",
        )
        emit_footer()
        return 0

    index_section = _find_index_section(compat)
    checklist_section = _find_checklist_section(compat)

    index_rows = _extract_temp_rows(index_section or compat, _ID_COLS)
    checklist_rows = _extract_temp_rows(checklist_section or compat, _ID_COLS)

    if not index_rows and not checklist_rows:
        emit_header(
            TOOL_NAME, mode, "SKIP", "NO_TEMP_IDS_FOUND",
            "No TEMPxx IDs found in ## Compatibility & Sunset section.",
        )
        emit_footer()
        return 0

    issues: list[str] = []

    # Set difference checks
    index_only = sorted(set(index_rows) - set(checklist_rows))
    checklist_only = sorted(set(checklist_rows) - set(index_rows))

    for tid in index_only:
        issues.append(
            f"{tid}: in Temporary Mechanism Index but missing from Sunset Closure Checklist"
        )
    for tid in checklist_only:
        issues.append(
            f"{tid}: in Sunset Closure Checklist but missing from Temporary Mechanism Index"
        )

    # Required field checks on checklist rows
    for tid, row in checklist_rows.items():
        for label, cols in (
            ("Retirement Trigger", _TRIGGER_COLS),
            ("Retirement Verification", _VERIFICATION_COLS),
            ("Removal Scope", _SCOPE_COLS),
        ):
            val = _get_col(row, cols).lower()
            if val in NONE_TOKENS:
                issues.append(f"{tid}: required field '{label}' is empty or TBD")

    # ADR file existence check
    for tid, row in index_rows.items():
        lifecycle = _get_col(row, _LIFECYCLE_COLS)
        if lifecycle:
            for match in ADR_PATH_RE.findall(lifecycle):
                adr_path = base_dir / match
                if not adr_path.exists():
                    issues.append(f"{tid}: lifecycle ADR file not found: {match}")

    overall = "FAIL" if issues else "PASS"
    code = "TEMP_LIFECYCLE_VIOLATIONS" if issues else "ALL_TEMP_LIFECYCLE_VALID"
    summary = (
        f"{len(issues)} TEMPxx lifecycle issue(s) found."
        if issues
        else f"All {len(index_rows)} TEMPxx mechanism(s) have valid lifecycle records."
    )

    emit_header(TOOL_NAME, mode, overall, code, summary)
    emit_line("signal.index_count", len(index_rows))
    emit_line("signal.checklist_count", len(checklist_rows))
    emit_line("signal.issues", len(issues))

    for i, issue in enumerate(issues, 1):
        emit_line(f"issue.{i}", issue)

    if issues:
        emit_line("fix.1", "FIX_ADD_MISSING_TEMP_CHECKLIST_ROW")
        emit_line("fix.2", "FIX_POPULATE_REQUIRED_LIFECYCLE_FIELDS")
        emit_line("fix.3", "FIX_RESOLVE_ADR_PATH")

    emit_footer()
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
