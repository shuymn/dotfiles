#!/usr/bin/env python3
"""Check that task DoD entries contain required risk tier annotations.

Usage:
  uv run --with pydantic python risk_dod_check.py plan.md design.md

Algorithm:
  1. Derive overall max risk tier from design.md ## Risk Classification.
  2. For each task in plan.md:
     - If max tier is Critical: require exact Critical DoD annotation.
     - If max tier is Sensitive (no Critical): require both Sensitive DoD annotations.
     - If max tier is Standard: check each task's Files for impl files;
       if impl files present, require Standard+impl annotation.
  3. Report tasks missing required annotations.

Conservative approach: the highest design tier applies to all tasks (no area-to-file mapping).
This prevents false negatives; acceptable false positives in mixed-tier designs.

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

TOOL_NAME = "risk-dod-check"

# Exact annotation strings as defined in decompose-plan SKILL.md Step 2.6
_DOD_CRITICAL = "Adversarial verification required (minimum 3 probes)."
_DOD_SENSITIVE_1 = "Heightened dod-recheck scrutiny applies."
_DOD_SENSITIVE_2 = (
    "Adversarial verification required"
    " (minimum 2 probes: Category 1 + most relevant 1 category)."
)
_DOD_STANDARD_IMPL = "Adversarial verification required (1 probe: most relevant category)."

# File path patterns that identify non-implementation (test/doc/config) files
_IMPL_EXCLUDE_RE = re.compile(
    r"(?:test|spec|\.md$|^docs/|\.txt$)", re.IGNORECASE
)

_TIER_ORDER = {"Critical": 3, "Sensitive": 2, "Standard": 1}


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


def parse_max_risk_tier(design_text: str) -> str:
    """Return the highest risk tier found in ## Risk Classification."""
    section = _extract_section(design_text, "Risk Classification")
    if not section:
        return "Standard"
    rows = _parse_table(section)
    max_tier = "Standard"
    for row in rows:
        tier = (row.get("Risk Tier") or row.get("risk_tier") or "Standard").strip()
        if _TIER_ORDER.get(tier, 0) > _TIER_ORDER.get(max_tier, 0):
            max_tier = tier
    return max_tier


def extract_tasks(plan_text: str) -> list[dict]:
    """Extract task id + body from plan.md."""
    tasks = []
    pattern = re.compile(
        r"^(### Task (\d+)\b[^\n]*\n.*?)(?=^### Task \d+|^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    for m in pattern.finditer(plan_text):
        tasks.append({"id": int(m.group(2)), "body": m.group(1)})
    return tasks


def _get_task_files(body: str) -> list[str]:
    """Extract file paths from Allowed Files or Files fields."""
    files: list[str] = []
    for field in ("Allowed Files", "Files"):
        pattern = re.compile(
            rf"^\s*-?\s*\*\*{re.escape(field)}\*\*:\s*\n((?:[ \t]+-[^\n]*\n?)*)",
            re.MULTILINE,
        )
        m = pattern.search(body)
        if m:
            for line in m.group(1).splitlines():
                stripped = line.strip()
                if stripped.startswith("- "):
                    payload = stripped[2:].strip()
                    bt = re.match(r"`([^`]+)`", payload)
                    files.append(bt.group(1) if bt else payload.split()[0] if payload else "")
    return [f for f in files if f]


def _has_impl_files(files: list[str]) -> bool:
    return any(not _IMPL_EXCLUDE_RE.search(f) for f in files)


def _get_dod_text(body: str) -> str:
    """Extract DoD text from task body."""
    # Match bold DoD field or DoD section
    m = re.search(
        r"\*\*DoD\*\*\s*:?\s*(.*?)(?=\*\*[A-Z]|\Z)",
        body,
        re.DOTALL,
    )
    return m.group(1) if m else body


def check_task(task_id: int, body: str, max_tier: str) -> list[str]:
    """Return list of issues for this task."""
    dod = _get_dod_text(body)
    issues: list[str] = []

    if max_tier == "Critical":
        if _DOD_CRITICAL not in dod:
            issues.append(
                f"Task {task_id} (Critical): missing DoD: {_DOD_CRITICAL!r}"
            )

    elif max_tier == "Sensitive":
        for annotation in (_DOD_SENSITIVE_1, _DOD_SENSITIVE_2):
            if annotation not in dod:
                issues.append(
                    f"Task {task_id} (Sensitive): missing DoD: {annotation!r}"
                )

    else:  # Standard
        files = _get_task_files(body)
        if _has_impl_files(files) and _DOD_STANDARD_IMPL not in dod:
            issues.append(
                f"Task {task_id} (Standard+impl): missing DoD: {_DOD_STANDARD_IMPL!r}"
            )

    return issues


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Risk tier DoD annotation check")
    parser.add_argument("plan_file", help="Path to plan.md")
    parser.add_argument("design_file", help="Path to design.md")
    args = parser.parse_args(argv[1:])

    mode = resolve_mode()
    plan_path = Path(args.plan_file)
    design_path = Path(args.design_file)

    for label, path in (("Plan", plan_path), ("Design", design_path)):
        if not path.exists():
            emit_header(
                TOOL_NAME, mode, "FAIL", f"{label.upper()}_FILE_NOT_FOUND",
                f"{label} file not found: {path}",
            )
            emit_line("fix.1", f"FIX_{label.upper()}_FILE_PATH")
            emit_footer()
            return 1

    plan_text = plan_path.read_text(encoding="utf-8")
    design_text = design_path.read_text(encoding="utf-8")

    max_tier = parse_max_risk_tier(design_text)
    tasks = extract_tasks(plan_text)

    if not tasks:
        emit_header(
            TOOL_NAME, mode, "SKIP", "NO_TASKS_FOUND",
            "No tasks found in plan.md.",
        )
        emit_footer()
        return 0

    all_issues: list[str] = []
    for task in tasks:
        all_issues.extend(check_task(task["id"], task["body"], max_tier))

    overall = "FAIL" if all_issues else "PASS"
    code = "RISK_DOD_ANNOTATIONS_MISSING" if all_issues else "ALL_RISK_DOD_ANNOTATIONS_PRESENT"
    summary = (
        f"{len(all_issues)} task(s) missing required risk tier DoD annotation(s)."
        if all_issues
        else f"All {len(tasks)} task(s) have required risk tier DoD annotations (tier={max_tier})."
    )

    emit_header(TOOL_NAME, mode, overall, code, summary)
    emit_line("signal.max_tier", max_tier)
    emit_line("signal.total_tasks", len(tasks))
    emit_line("signal.issues", len(all_issues))

    for i, issue in enumerate(all_issues, 1):
        emit_line(f"issue.{i}", issue)

    if all_issues:
        emit_line("fix.1", "FIX_ADD_ADVERSARIAL_VERIFICATION_DOD_LINE")
        emit_line("fix.2", "FIX_ADD_HEIGHTENED_SCRUTINY_DOD_LINE")

    emit_footer()
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
