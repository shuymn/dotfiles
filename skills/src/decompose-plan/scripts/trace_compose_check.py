#!/usr/bin/env python3
"""Cross-reference checks between design.md and plan.trace.md.

Checks:
  B: Trace-XRef — forward/reverse fidelity of design atoms in trace matrix
  C: AC-Ownership — AC coverage in ownership map
  D: TEMP-Trace — temporal ID matching in temporary mechanism trace

Output: LLM_CHECK_V2 format (via shared llm_check helper).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from llm_check import (  # noqa: E402
    emit_footer,
    emit_header,
    emit_line,
    resolve_mode,
    sanitize,
)

TOOL_NAME = "trace-compose-check"

ATOM_PATTERNS = {
    "REQ": re.compile(r"REQ[A-Za-z0-9_-]*[0-9]+"),
    "AC": re.compile(r"AC[A-Za-z0-9_-]*[0-9]+"),
    "GOAL": re.compile(r"GOAL[A-Za-z0-9_-]*[0-9]+"),
    "DEC": re.compile(r"DEC[A-Za-z0-9_-]*[0-9]+"),
}
TEMP_PATTERN = re.compile(r"TEMP[A-Za-z0-9_-]*[0-9]+")


def extract_section(text: str, title: str) -> str:
    """Extract content under a ## heading until the next ## or end."""
    pattern = re.compile(
        rf"(?ms)^## {re.escape(title)}\s*$\n(.*?)(?=^## |\Z)"
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def extract_design_atoms(design_text: str) -> set[str]:
    """Extract all REQ, AC, GOAL, DEC atoms from design text."""
    atoms: set[str] = set()
    for pattern in ATOM_PATTERNS.values():
        atoms.update(pattern.findall(design_text))
    return atoms


def extract_design_acs(design_text: str) -> set[str]:
    return set(ATOM_PATTERNS["AC"].findall(design_text))


def extract_design_temps(design_text: str) -> set[str]:
    return set(TEMP_PATTERN.findall(design_text))


def parse_trace_matrix_atoms(section_text: str) -> set[str]:
    """Parse `- ATOM: Task N, Task M` bullet lines from trace matrix."""
    atoms: set[str] = set()
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        payload = stripped[2:]
        colon_pos = payload.find(":")
        if colon_pos < 0:
            continue
        atom_part = payload[:colon_pos].strip()
        for pattern in ATOM_PATTERNS.values():
            atoms.update(pattern.findall(atom_part))
    return atoms


def parse_ac_ownership_map(section_text: str) -> list[dict[str, str]]:
    """Parse AC Ownership Map table rows."""
    rows: list[dict[str, str]] = []
    lines = [
        line.strip()
        for line in section_text.splitlines()
        if line.strip().startswith("|")
    ]
    if len(lines) < 2:
        return rows

    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    data_start = 1
    if len(lines) > 1:
        sep_cells = [cell.strip() for cell in lines[1].strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c or "") for c in sep_cells):
            data_start = 2

    for line in lines[data_start:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def parse_temp_trace_ids(section_text: str) -> set[str]:
    """Parse TEMP IDs from Temporary Mechanism Trace section (bullet or table)."""
    temps: set[str] = set()
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            payload = stripped[2:]
            colon_pos = payload.find(":")
            atom = payload[:colon_pos].strip() if colon_pos >= 0 else payload.strip()
            temps.update(TEMP_PATTERN.findall(atom))
        elif stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if cells:
                temps.update(TEMP_PATTERN.findall(cells[0]))
    return temps


def check_trace_xref(
    design_atoms: set[str], trace_atoms: set[str]
) -> tuple[str, str, str]:
    """Check B: Forward/Reverse fidelity."""
    missing_forward = sorted(design_atoms - trace_atoms)
    orphan_reverse = sorted(trace_atoms - design_atoms)
    issues: list[str] = []
    if missing_forward:
        issues.append(f"missing in trace: {', '.join(missing_forward)}")
    if orphan_reverse:
        issues.append(f"orphan in trace: {', '.join(orphan_reverse)}")

    if issues:
        return ("FAIL", "Design atom trace mismatch.", "; ".join(issues))
    return ("PASS", "All design atoms matched in trace matrix.", "")


def check_ac_ownership(
    design_acs: set[str], ownership_rows: list[dict[str, str]]
) -> tuple[str, str, str]:
    """Check C: AC Ownership coverage."""
    map_acs: set[str] = set()
    owner_by_ac: dict[str, list[str]] = {}
    for row in ownership_rows:
        ac_id = row.get("AC ID", "").strip()
        owner = row.get("Owner Task", "").strip()
        if ac_id:
            map_acs.add(ac_id)
            owner_by_ac.setdefault(ac_id, []).append(owner)

    missing = sorted(design_acs - map_acs)
    phantom = sorted(map_acs - design_acs)
    duplicates = sorted(ac for ac, owners in owner_by_ac.items() if len(owners) > 1)

    issues: list[str] = []
    if missing:
        issues.append(f"missing from ownership: {', '.join(missing)}")
    if phantom:
        issues.append(f"phantom in ownership: {', '.join(phantom)}")
    if duplicates:
        issues.append(f"duplicate owner: {', '.join(duplicates)}")

    if issues:
        return ("FAIL", "AC ownership map mismatch.", "; ".join(issues))
    return ("PASS", "All design ACs covered in ownership map.", "")


def check_temp_trace(
    design_temps: set[str], trace_temps: set[str]
) -> tuple[str, str, str]:
    """Check D: Temporal ID matching."""
    missing = sorted(design_temps - trace_temps)
    orphan = sorted(trace_temps - design_temps)
    issues: list[str] = []
    if missing:
        issues.append(f"missing in trace: {', '.join(missing)}")
    if orphan:
        issues.append(f"orphan in trace: {', '.join(orphan)}")

    if issues:
        return ("FAIL", "TEMP ID trace mismatch.", "; ".join(issues))
    return ("PASS", "All TEMP IDs matched in trace.", "")


FIX_CODES = {
    "Trace-XRef": "FIX_UPDATE_TRACE_MATRIX",
    "AC-Ownership": "FIX_UPDATE_AC_OWNERSHIP_MAP",
    "TEMP-Trace": "FIX_UPDATE_TEMP_TRACE",
}


def emit_result(
    mode: str,
    checks: list[tuple[str, str, str, str]],
) -> int:
    """Emit LLM_CHECK_V2 output. checks = [(id, status, summary, evidence), ...]"""
    total = len(checks)
    failed = [c for c in checks if c[1] == "FAIL"]
    overall = "FAIL" if failed else "PASS"
    code = "TRACE_COMPOSE_CHECK_FAILED" if failed else "ALL_CHECKS_PASSED"
    overall_summary = (
        f"{len(failed)} of {total} trace/compose checks failed."
        if failed
        else f"All {total} trace/compose checks passed."
    )

    emit_header(TOOL_NAME, mode, overall, code, overall_summary)
    emit_line("checks.total", total)
    emit_line("checks.failed", len(failed))

    if mode == "full":
        for i, (cid, status, summary, evidence) in enumerate(checks, 1):
            emit_line(f"check.{i}.id", cid)
            emit_line(f"check.{i}.status", status)
            emit_line(f"check.{i}.summary", summary)
            if evidence:
                emit_line(f"check.{i}.evidence", evidence)

    if mode == "compact" and failed:
        for i, (cid, _status, _summary, evidence) in enumerate(
            [c for c in checks if c[1] == "FAIL"], 1
        ):
            fix = FIX_CODES.get(cid, "FIX_RERUN_AFTER_CORRECTION")
            ev = sanitize(evidence)
            if len(ev) > 80:
                ev = ev[:80] + "..."
            if ev:
                emit_line(f"fail.{i}", f"{cid}|e={ev}|fix={fix}")
            else:
                emit_line(f"fail.{i}", f"{cid}|fix={fix}")

    emit_footer()
    return 0 if overall == "PASS" else 1


def _emit_early_fail(mode: str, code: str, summary: str, fix: str) -> None:
    emit_header(TOOL_NAME, mode, "FAIL", code, summary)
    emit_line("fix.1", fix)
    emit_footer()


def main(argv: list[str]) -> int:
    mode = resolve_mode()

    if len(argv) != 3:
        _emit_early_fail(mode, "INVALID_ARGUMENT_COUNT",
                         "Expected exactly 2 arguments: <design-file> <plan-trace-file>.",
                         "FIX_USE_TWO_ARGS")
        return 1

    design_path = Path(argv[1])
    trace_path = Path(argv[2])

    fix_codes = {"Design": "FIX_DESIGN_FILE_PATH", "Trace": "FIX_TRACE_FILE_PATH"}
    for label, path in [("Design", design_path), ("Trace", trace_path)]:
        if not path.exists():
            _emit_early_fail(mode, f"{label.upper()}_FILE_NOT_FOUND",
                             f"{label} file not found: {path}", fix_codes[label])
            return 1

    design_text = design_path.read_text(encoding="utf-8")
    trace_text = trace_path.read_text(encoding="utf-8")

    # Check B: Trace-XRef
    design_atoms = extract_design_atoms(design_text)
    trace_section = extract_section(trace_text, "Design -> Task Trace Matrix")
    trace_atoms = parse_trace_matrix_atoms(trace_section)
    b_status, b_summary, b_evidence = check_trace_xref(design_atoms, trace_atoms)

    # Check C: AC-Ownership
    design_acs = extract_design_acs(design_text)
    ac_section = extract_section(trace_text, "AC Ownership Map")
    ac_rows = parse_ac_ownership_map(ac_section)
    c_status, c_summary, c_evidence = check_ac_ownership(design_acs, ac_rows)

    # Check D: TEMP-Trace
    design_temps = extract_design_temps(design_text)
    temp_section = extract_section(trace_text, "Temporary Mechanism Trace")
    trace_temps = parse_temp_trace_ids(temp_section)
    d_status, d_summary, d_evidence = check_temp_trace(design_temps, trace_temps)

    checks = [
        ("Trace-XRef", b_status, b_summary, b_evidence),
        ("AC-Ownership", c_status, c_summary, c_evidence),
        ("TEMP-Trace", d_status, d_summary, d_evidence),
    ]

    return emit_result(mode, checks)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
