#!/usr/bin/env python3
"""Generate a Task Dependency Graph section from plan.md Dependencies fields.

Output: LLM_CHECK_V2 format on stdout. Side effect: plan.md in-place update.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from llm_check import emit_footer, emit_header, emit_line, resolve_mode  # noqa: E402

TOOL_NAME = "dep-graph-gen"


def parse_tasks_with_deps(plan_text: str) -> list[tuple[int, tuple[str, ...]]]:
    """Parse ### Task N headers and their **Dependencies** fields."""
    tasks: list[tuple[int, tuple[str, ...]]] = []
    current_task: int | None = None

    for line in plan_text.splitlines():
        task_match = re.match(r"^### Task (\d+)", line)
        if task_match:
            current_task = int(task_match.group(1))
            continue

        if current_task is not None:
            dep_match = re.match(
                r"^-?\s*\*\*Dependencies\*\*:\s*(.*)", line
            )
            if dep_match:
                raw = dep_match.group(1).strip()
                deps = _parse_dep_value(raw)
                tasks.append((current_task, deps))
                current_task = None

    if current_task is not None:
        tasks.append((current_task, ()))

    return tasks


_NONE_TOKENS = {"", "-", "none", "n/a", "na"}


def _parse_dep_value(value: str) -> tuple[str, ...]:
    normalized = re.sub(r"\s+", " ", value.strip().casefold())
    if normalized in _NONE_TOKENS:
        return ()
    refs = re.findall(r"T(\d+)", value)
    return tuple(f"T{r}" for r in refs)


def generate_dep_graph(tasks: list[tuple[int, tuple[str, ...]]]) -> str:
    """Generate the dependency graph section content."""
    roots = [t for t, deps in tasks if not deps]
    has_deps = [(t, deps) for t, deps in tasks if deps]

    lines = ["## Task Dependency Graph", ""]
    if roots:
        root_labels = ", ".join(f"T{t}" for t in sorted(roots))
        lines.append(f"Roots (no dependencies): {root_labels}")
    else:
        lines.append("Roots (no dependencies): (none)")

    if has_deps:
        lines.append("")
        for task_id, deps in sorted(has_deps, key=lambda x: x[0]):
            dep_str = ", ".join(sorted(deps, key=lambda d: int(d[1:])))
            lines.append(f"- T{task_id}: {dep_str}")

    return "\n".join(lines)


def patch_plan(plan_text: str, graph_section: str) -> str:
    """Insert or replace ## Task Dependency Graph in plan text."""
    existing = re.search(
        r"^## Task Dependency Graph\n.*?(?=^## |\Z)",
        plan_text,
        re.MULTILINE | re.DOTALL,
    )
    if existing:
        return (
            plan_text[: existing.start()]
            + graph_section
            + "\n\n"
            + plan_text[existing.end():].lstrip("\n")
        )

    task_match = re.search(r"^### Task \d+", plan_text, re.MULTILINE)
    if task_match:
        insert_pos = task_match.start()
        return (
            plan_text[:insert_pos].rstrip("\n")
            + "\n\n"
            + graph_section
            + "\n\n"
            + plan_text[insert_pos:]
        )

    return plan_text.rstrip("\n") + "\n\n" + graph_section + "\n"


def _emit_fail(mode: str, code: str, summary: str, fix: str) -> None:
    emit_header(TOOL_NAME, mode, "FAIL", code, summary)
    emit_line("fix.1", fix)
    emit_footer()


def main(argv: list[str]) -> int:
    mode = resolve_mode()

    if len(argv) != 2:
        _emit_fail(mode, "INVALID_ARGUMENT_COUNT",
                   "Expected exactly 1 argument: <plan-file>.", "FIX_USE_ONE_ARG")
        return 1

    plan_path = Path(argv[1])
    if not plan_path.exists():
        _emit_fail(mode, "PLAN_FILE_NOT_FOUND",
                   f"Plan file not found: {plan_path}", "FIX_PLAN_FILE_PATH")
        return 1

    plan_text = plan_path.read_text(encoding="utf-8")
    tasks = parse_tasks_with_deps(plan_text)
    if not tasks:
        _emit_fail(mode, "NO_TASKS_FOUND",
                   "No ### Task N headers found in plan file.", "FIX_ADD_TASK_HEADERS")
        return 1

    graph = generate_dep_graph(tasks)
    patched = patch_plan(plan_text, graph)
    plan_path.write_text(patched, encoding="utf-8")

    roots = [t for t, deps in tasks if not deps]
    dep_count = sum(len(deps) for _, deps in tasks)

    emit_header(TOOL_NAME, mode, "PASS", "GRAPH_GENERATED",
                f"Generated dependency graph for {len(tasks)} tasks.")
    emit_line("signal.task_count", len(tasks))
    emit_line("signal.root_count", len(roots))
    emit_line("signal.dep_edge_count", dep_count)
    emit_footer()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
