#!/usr/bin/env python3
"""Verify that changed files fall within a task's Allowed/Exception Files scope.

Usage:
  git diff --name-only HEAD~1 | uv run python file_scope_check.py plan.md --task 3

Output: LLM_CHECK_V2 format (via shared llm_check helper).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from llm_check import emit_footer, emit_header, emit_line, resolve_mode  # noqa: E402

TOOL_NAME = "file-scope-check"


@dataclass(frozen=True)
class FileMatch:
    path: str
    pattern: str
    status: str  # "OK" | "OK (exception)" | "SCOPE_DEVIATION"


def extract_task_block(plan_text: str, task_id: int) -> str:
    """Extract the text block for ### Task N until the next ### Task or ## heading."""
    pattern = re.compile(
        rf"^### Task {task_id}\b[^\n]*\n(.*?)(?=^### Task \d+|^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(plan_text)
    return match.group(0) if match else ""


def parse_allowed_files(block: str) -> list[str]:
    """Parse Allowed Files glob patterns from a task block."""
    return _parse_file_list(block, "Allowed Files")


def parse_exception_files(block: str) -> list[tuple[str, str]]:
    """Parse Exception Files with rationale from a task block."""
    section = _extract_field_list(block, "Exception Files")
    results: list[tuple[str, str]] = []
    for line in section:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        payload = stripped[2:].strip()
        bt_match = re.match(r"`([^`]+)`\s*(?:\(([^)]*)\))?", payload)
        if bt_match:
            results.append((bt_match.group(1), bt_match.group(2) or ""))
        else:
            paren_match = re.match(r"(\S+)\s*(?:\(([^)]*)\))?", payload)
            if paren_match:
                results.append((paren_match.group(1), paren_match.group(2) or ""))
    return results


def _extract_field_list(block: str, field_name: str) -> list[str]:
    """Extract indented list items following a **Field Name**: line."""
    pattern = re.compile(
        rf"^-?\s*\*\*{re.escape(field_name)}\*\*:\s*\n((?:[ \t]+-[^\n]*\n?)*)",
        re.MULTILINE,
    )
    match = pattern.search(block)
    if not match:
        return []
    return match.group(1).splitlines()


def _parse_file_list(block: str, field_name: str) -> list[str]:
    """Parse a list of glob patterns from a field."""
    lines = _extract_field_list(block, field_name)
    patterns: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        payload = stripped[2:].strip()
        bt_match = re.match(r"`([^`]+)`", payload)
        if bt_match:
            patterns.append(bt_match.group(1))
        elif payload:
            patterns.append(payload.split()[0])
    return patterns


def match_file(
    path: str,
    allowed: list[str],
    exceptions: list[tuple[str, str]],
) -> FileMatch:
    """Match a file path against allowed patterns and exception patterns."""
    posix_path = PurePosixPath(path)

    for pattern in allowed:
        if posix_path.full_match(pattern):
            return FileMatch(path=path, pattern=pattern, status="OK")

    for pattern, _rationale in exceptions:
        if posix_path.full_match(pattern):
            return FileMatch(
                path=path,
                pattern=f"EXCEPTION({pattern})",
                status="OK (exception)",
            )

    return FileMatch(path=path, pattern="NONE", status="SCOPE_DEVIATION")


def _emit_result(mode: str, matches: list[FileMatch], task_id: int) -> int:
    """Emit LLM_CHECK_V2 structured result."""
    deviations = [m for m in matches if m.status == "SCOPE_DEVIATION"]
    ok_count = sum(1 for m in matches if m.status == "OK")
    exception_count = sum(1 for m in matches if m.status == "OK (exception)")
    overall = "FAIL" if deviations else "PASS"
    code = "SCOPE_DEVIATION_DETECTED" if deviations else "ALL_FILES_IN_SCOPE"
    summary = (
        f"{len(deviations)} file(s) outside allowed scope for Task {task_id}."
        if deviations
        else f"All {len(matches)} file(s) within scope for Task {task_id}."
    )

    emit_header(TOOL_NAME, mode, overall, code, summary)
    emit_line("signal.task", task_id)
    emit_line("signal.total_files", len(matches))
    emit_line("signal.ok", ok_count)
    emit_line("signal.exception", exception_count)
    emit_line("signal.deviation", len(deviations))

    for i, m in enumerate(matches, 1):
        emit_line(f"file.{i}", f"{m.path}|pattern={m.pattern}|status={m.status}")

    if deviations:
        emit_line("evidence", ", ".join(m.path for m in deviations))
        emit_line("fix.1", "FIX_ADD_TO_ALLOWED_OR_EXCEPTION_FILES")
        emit_line("fix.2", "FIX_REVERT_OUT_OF_SCOPE_CHANGES")

    emit_footer()
    return 0 if overall == "PASS" else 1


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="File scope verification")
    parser.add_argument("plan_file", help="Path to plan.md")
    parser.add_argument("--task", type=int, required=True, help="Task number")
    args = parser.parse_args(argv[1:])

    mode = resolve_mode()
    plan_path = Path(args.plan_file)

    if not plan_path.exists():
        emit_header(TOOL_NAME, mode, "FAIL", "PLAN_FILE_NOT_FOUND",
                     f"Plan file not found: {plan_path}")
        emit_line("fix.1", "FIX_PLAN_FILE_PATH")
        emit_footer()
        return 1

    plan_text = plan_path.read_text(encoding="utf-8")
    block = extract_task_block(plan_text, args.task)
    if not block:
        emit_header(TOOL_NAME, mode, "FAIL", "TASK_NOT_FOUND",
                     f"Task {args.task} not found in plan.")
        emit_line("fix.1", "FIX_CHECK_TASK_ID")
        emit_footer()
        return 1

    allowed = parse_allowed_files(block)
    if not allowed:
        emit_header(TOOL_NAME, mode, "SKIP", "NO_ALLOWED_FILES",
                     f"No Allowed Files defined for Task {args.task}. Scope check skipped.")
        emit_footer()
        return 0

    exceptions = parse_exception_files(block)

    changed_files = [
        line.strip() for line in sys.stdin if line.strip()
    ]
    if not changed_files:
        emit_header(TOOL_NAME, mode, "SKIP", "NO_CHANGED_FILES",
                     "No changed files provided on stdin.")
        emit_footer()
        return 0

    matches = [match_file(f, allowed, exceptions) for f in changed_files]
    return _emit_result(mode, matches, args.task)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
