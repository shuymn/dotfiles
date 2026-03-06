#!/usr/bin/env python3
"""Validate structural format of skill workflow artifacts.

Usage:
  uv run --with pydantic python artifact_format_check.py <artifact.md> --type <type>

  type: design | plan | trace | compose | review | dod-recheck | adversarial

Checks per type:
  - Required section headings exist
  - All markdown tables have a separator row and consistent column counts
  - Stable IDs (GOALxx, REQxx, ACxx, DECxx, TEMPxx) follow [A-Z]+[0-9]{2,} format
    when they appear in ID-bearing columns

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

TOOL_NAME = "artifact-format-check"

# Required sections per artifact type (heading text, case-insensitive partial match)
_REQUIRED_SECTIONS: dict[str, list[str]] = {
    "design": [
        "Goals",
        "Acceptance Criteria",
        "Decomposition Strategy",
    ],
    "plan": [
        "Checkpoint Summary",
        "Task Dependency Graph",
    ],
    "trace": [
        "Design -> Task Trace Matrix",
        "AC Ownership Map",
    ],
    "compose": [
        # compose is reconstructed output; check only non-empty content
    ],
    "review": [],          # checked via Overall Verdict line below
    "dod-recheck": [],     # checked via Overall Verdict line below
    "adversarial": [
        "Attack Summary",
    ],
}

# Types that require an "Overall Verdict:" metadata line
_REQUIRES_OVERALL_VERDICT = {"review", "dod-recheck", "adversarial"}

# ID columns that should contain stable IDs with 2+ digit suffix
_ID_COLUMN_HINTS = re.compile(
    r"^(?:AC\s*ID|GOAL\s*ID|REQ\s*ID|DEC\s*ID|TEMP\s*ID|id)$",
    re.IGNORECASE,
)
_VALID_ID_RE = re.compile(r"^[A-Z]{2,}[0-9]{2,}$")
_INVALID_ID_RE = re.compile(r"^[A-Z]{2,}[0-9]{1}$")  # only 1 digit suffix

_SECTION_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
_OVERALL_VERDICT_RE = re.compile(
    r"^[- ]*\*{0,2}Overall Verdict\*{0,2}\s*:\s*(\w+)",
    re.MULTILINE,
)


def _find_sections(text: str) -> list[str]:
    """Return list of all section heading texts (lowercased)."""
    return [m.group(2).strip().lower() for m in _SECTION_RE.finditer(text)]


def _check_required_sections(
    text: str, artifact_type: str
) -> list[str]:
    """Return list of missing required section headings."""
    required = _REQUIRED_SECTIONS.get(artifact_type, [])
    found = _find_sections(text)
    missing: list[str] = []
    for req in required:
        req_lower = req.lower()
        if not any(req_lower in heading for heading in found):
            missing.append(req)
    return missing


def _check_overall_verdict(text: str) -> list[str]:
    """Return issue if Overall Verdict line is missing or has invalid value."""
    m = _OVERALL_VERDICT_RE.search(text)
    if not m:
        return ["missing 'Overall Verdict: PASS | FAIL' metadata line"]
    val = m.group(1).upper()
    if val not in ("PASS", "FAIL"):
        return [f"Overall Verdict has invalid value: {val!r} (must be PASS or FAIL)"]
    return []


def _check_table_structure(text: str) -> list[str]:
    """Check all markdown tables: separator row exists, column counts consistent."""
    issues: list[str] = []
    # Find table blocks (consecutive lines starting with |)
    current_block: list[tuple[int, str]] = []
    in_table = False

    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("|"):
            current_block.append((lineno, stripped))
            in_table = True
        else:
            if in_table and len(current_block) >= 2:
                issues.extend(_validate_table_block(current_block))
            current_block = []
            in_table = False

    if in_table and len(current_block) >= 2:
        issues.extend(_validate_table_block(current_block))

    return issues


def _validate_table_block(block: list[tuple[int, str]]) -> list[str]:
    issues: list[str] = []
    if len(block) < 2:
        return issues

    first_lineno, header_line = block[0]
    header_cols = len(header_line.strip("|").split("|"))

    # Check separator row (row index 1)
    _, sep_line = block[1]
    sep_cells = [c.strip() for c in sep_line.strip("|").split("|")]
    if not all(re.fullmatch(r":?-{2,}:?", c or "-") for c in sep_cells):
        issues.append(
            f"table at line {first_lineno}: row 2 is not a valid separator"
            f" (got: {sep_line[:60]!r})"
        )
        return issues  # can't validate further without valid separator

    # Check data rows for column count consistency
    for lineno, line in block[2:]:
        cols = len(line.strip("|").split("|"))
        if cols != header_cols:
            issues.append(
                f"table at line {first_lineno}: row at line {lineno}"
                f" has {cols} columns, expected {header_cols}"
            )

    return issues


def _check_id_format(text: str) -> list[str]:
    """Check that stable IDs in ID-column cells follow [A-Z]{{2+}}[0-9]{{2+}} format."""
    issues: list[str] = []
    lines = text.splitlines()
    headers: list[str] = []
    in_table = False

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not in_table:
                # This is a header row
                headers = cells
                in_table = True
                continue
            # Check separator row
            if all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells):
                continue
            # Data row: check ID columns
            for col_idx, cell in enumerate(cells):
                if col_idx >= len(headers):
                    break
                if not _ID_COLUMN_HINTS.match(headers[col_idx]):
                    continue
                # Cell should be a valid stable ID if it looks like one
                if _INVALID_ID_RE.match(cell):
                    issues.append(
                        f"line {lineno}: ID {cell!r} in column {headers[col_idx]!r}"
                        " uses 1-digit suffix; stable IDs require 2+ digits (e.g., AC01)"
                    )
        else:
            in_table = False
            headers = []

    return issues


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Artifact format validation")
    parser.add_argument("artifact_file", help="Path to artifact markdown file")
    parser.add_argument(
        "--type",
        dest="artifact_type",
        required=True,
        choices=list(_REQUIRED_SECTIONS.keys()),
        help="Artifact type",
    )
    args = parser.parse_args(argv[1:])

    mode = resolve_mode()
    artifact_path = Path(args.artifact_file)

    if not artifact_path.exists():
        emit_header(
            TOOL_NAME, mode, "FAIL", "ARTIFACT_FILE_NOT_FOUND",
            f"Artifact file not found: {artifact_path}",
        )
        emit_line("fix.1", "FIX_ARTIFACT_FILE_PATH")
        emit_footer()
        return 1

    text = artifact_path.read_text(encoding="utf-8")

    if not text.strip():
        emit_header(
            TOOL_NAME, mode, "FAIL", "ARTIFACT_FILE_EMPTY",
            f"Artifact file is empty: {artifact_path}",
        )
        emit_line("fix.1", "FIX_WRITE_ARTIFACT_CONTENT")
        emit_footer()
        return 1

    artifact_type = args.artifact_type
    issues: list[str] = []

    # 1. Required sections
    missing_sections = _check_required_sections(text, artifact_type)
    for sec in missing_sections:
        issues.append(f"missing required section: ## {sec}")

    # 2. Overall Verdict (for applicable types)
    if artifact_type in _REQUIRES_OVERALL_VERDICT:
        issues.extend(_check_overall_verdict(text))

    # 3. Table structure
    issues.extend(_check_table_structure(text))

    # 4. ID format
    issues.extend(_check_id_format(text))

    overall = "FAIL" if issues else "PASS"
    code = "ARTIFACT_FORMAT_VIOLATIONS" if issues else "ARTIFACT_FORMAT_VALID"
    summary = (
        f"{len(issues)} format violation(s) in {artifact_type} artifact."
        if issues
        else f"{artifact_type} artifact passed all format checks."
    )

    emit_header(TOOL_NAME, mode, overall, code, summary)
    emit_line("signal.artifact_type", artifact_type)
    emit_line("signal.issues", len(issues))

    for i, issue in enumerate(issues, 1):
        emit_line(f"issue.{i}", issue)

    if issues:
        emit_line("fix.1", "FIX_ADD_MISSING_SECTION_HEADINGS")
        emit_line("fix.2", "FIX_REPAIR_TABLE_SEPARATOR_OR_COLUMN_COUNT")
        emit_line("fix.3", "FIX_USE_TWO_DIGIT_ID_SUFFIX")

    emit_footer()
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
