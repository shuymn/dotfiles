#!/usr/bin/env python3
"""Check that every AC row in a design doc has a populated Verification Command.

Usage:
  uv run --with pydantic python verification_cmd_check.py design.md

Checks:
  - Empty verification command → FAIL
  - "TBD-at-plan" → PASS with advisory (decompose-plan resolves it)
  - Concrete command → first whitespace-delimited token checked via shutil.which()

Output: LLM_CHECK_V2 format (via shared llm_check helper).
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from llm_check import emit_footer, emit_header, emit_line, resolve_mode  # noqa: E402

TOOL_NAME = "verification-cmd-check"
TBD_TOKEN = "tbd-at-plan"
NONE_TOKENS = {"", "-", "none", "n/a", "na", "tbd"}


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


def parse_ac_rows(text: str) -> list[dict[str, str]]:
    """Extract AC table rows from design text."""
    section = _extract_section(text, "Acceptance Criteria")
    if not section:
        return []
    return _parse_table(section)


def check_row(row: dict[str, str]) -> tuple[str, str]:
    """Return (status, message). status: PASS | TBD | FAIL."""
    cmd = (
        row.get("Verification Command")
        or row.get("verification_command")
        or row.get("Verification")
        or ""
    ).strip()
    ac_id = (row.get("AC ID") or row.get("ac_id") or "?").strip()

    normalized = cmd.lower().replace("-", "").replace("_", "").replace(" ", "")
    if not cmd or normalized in NONE_TOKENS:
        return ("FAIL", f"{ac_id}: verification command is empty")

    if cmd.lower() == TBD_TOKEN or cmd.lower().replace("-", "").replace("_", "") == "tbdatplan":
        return ("TBD", f"{ac_id}: TBD-at-plan (decompose-plan must resolve)")

    first_token = cmd.split()[0]
    if shutil.which(first_token) is None:
        return ("FAIL", f"{ac_id}: command not found via command -v: {first_token!r}")

    return ("PASS", "")


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify Verification Command column in AC table"
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
    rows = parse_ac_rows(text)

    if not rows:
        emit_header(
            TOOL_NAME, mode, "SKIP", "NO_AC_TABLE",
            "No Acceptance Criteria table found in design file.",
        )
        emit_footer()
        return 0

    failures: list[str] = []
    advisories: list[str] = []

    for row in rows:
        status, msg = check_row(row)
        if status == "FAIL":
            failures.append(msg)
        elif status == "TBD":
            advisories.append(msg)

    overall = "FAIL" if failures else "PASS"
    code = "VERIFICATION_CMD_ISSUES" if failures else "ALL_VERIFICATION_COMMANDS_OK"
    summary = (
        f"{len(failures)} AC(s) have missing or unresolvable verification command(s)."
        if failures
        else f"All {len(rows)} AC(s) have valid verification commands."
    )

    emit_header(TOOL_NAME, mode, overall, code, summary)
    emit_line("signal.total_acs", len(rows))
    emit_line("signal.failures", len(failures))
    emit_line("signal.advisories", len(advisories))

    for i, msg in enumerate(failures, 1):
        emit_line(f"fail.{i}", msg)
    for i, msg in enumerate(advisories, 1):
        emit_line(f"advisory.{i}", msg)

    if failures:
        emit_line("fix.1", "FIX_POPULATE_VERIFICATION_COMMAND")
        emit_line("fix.2", "FIX_INSTALL_MISSING_COMMAND_OR_USE_TBD_AT_PLAN")

    emit_footer()
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
