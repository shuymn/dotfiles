#!/usr/bin/env python3
"""Finalize a plan review draft into the gate artifact consumed downstream."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SUMMARY_FIELDS = [
    "Forward Fidelity",
    "Reverse Fidelity",
    "Round-trip",
    "Behavioral Lock",
    "Negative Path",
    "Temporal",
    "Traceability",
    "Scope",
    "Testability",
    "Execution Readiness",
    "Integration Coverage",
    "Risk Classification",
]
SUMMARY_NA_FIELDS = {"Integration Coverage", "Risk Classification"}
ALLOWED_CARDS = {1, 2, 3, 5, 8}
AXES = ("Objective", "Surface", "Verification", "Rollback")


@dataclass
class MachineRow:
    task: str
    total: str
    verdict: str
    trigger: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize decompose-plan review output")
    parser.add_argument("plan_file", help="Path to plan.md")
    parser.add_argument("draft_file", help="Path to plan.review.draft.md")
    parser.add_argument("final_file", help="Path to plan.review.md")
    return parser.parse_args()


def extract_section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## [^\n]+\n|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    return match.group("body").strip("\n") if match else ""


def normalize_field_name(raw: str) -> str:
    return raw.replace("**", "").strip()


def canonicalize_summary_value(field: str, raw: str | None) -> tuple[str, str | None]:
    if raw is None:
        return ("FAIL", f"Summary is missing `{field}`.")

    value = raw.strip()
    if value.startswith("PASS"):
        return ("PASS", None)
    if value.startswith("FAIL"):
        return ("FAIL", None)
    if value.startswith("N/A"):
        if field in SUMMARY_NA_FIELDS:
            return (value, None)
        return ("FAIL", f"`{field}` cannot be `N/A`.")

    return ("FAIL", f"`{field}` has an invalid verdict: `{value}`.")


def parse_summary(summary_body: str) -> tuple[dict[str, str], list[str]]:
    raw_map: dict[str, str] = {}
    errors: list[str] = []

    for line in summary_body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        payload = stripped[2:]
        if ":" not in payload:
            continue
        name, value = payload.split(":", 1)
        raw_map[normalize_field_name(name)] = value.strip()

    final_map: dict[str, str] = {}
    for field in SUMMARY_FIELDS:
        verdict, error = canonicalize_summary_value(field, raw_map.get(field))
        final_map[field] = verdict
        if error:
            errors.append(error)

    return final_map, errors


def parse_plan_tasks(plan_text: str) -> list[str]:
    return [f"Task {match.group(1)}" for match in re.finditer(r"^### Task (\d+):", plan_text, re.MULTILINE)]


def parse_plan_title(plan_text: str, plan_path: Path) -> str:
    match = re.search(r"^# (.+)$", plan_text, re.MULTILINE)
    if not match:
        return f"{plan_path.parent.name} - Plan Review"

    title = match.group(1).strip()
    if title.endswith(" Implementation Plan"):
        title = title.removesuffix(" Implementation Plan")
    return f"{title} - Plan Review"


def parse_design_path(plan_text: str, plan_path: Path) -> Path:
    match = re.search(r"^- \*\*Source\*\*: `([^`]+)`", plan_text, re.MULTILINE)
    if match:
        source = Path(match.group(1))
        return source if source.is_absolute() else (Path.cwd() / source).resolve()
    return (plan_path.parent / "design.md").resolve()


def parse_granularity_table(body: str) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    found_header = False

    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or all(not cell for cell in cells):
            continue
        if cells[0] == "Task":
            found_header = True
            continue
        if re.fullmatch(r"-{3,}", cells[0]):
            continue
        if len(cells) != 6:
            errors.append(f"Malformed granularity row: `{stripped}`.")
            continue
        rows.append(
            {
                "task": cells[0],
                "Objective": cells[1],
                "Surface": cells[2],
                "Verification": cells[3],
                "Rollback": cells[4],
                "Evidence": cells[5],
            }
        )

    if not found_header:
        errors.append("Granularity Poker table header is missing.")

    return rows, errors


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def get_digest_stamp(script_dir: Path, plan_file: Path) -> str:
    result = run_command([str(script_dir / "digest-stamp.sh"), "plan-review", str(plan_file)])
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip() or "digest-stamp.sh failed")
    return result.stdout.strip()


def run_structural_check(script_dir: Path, design_file: Path, plan_file: Path) -> tuple[bool, str]:
    result = run_command(
        [str(script_dir / "structural-check.sh"), str(design_file), str(plan_file)]
    )
    if result.returncode == 0:
        return (True, result.stdout.strip())
    evidence = result.stdout.strip() or result.stderr.strip() or "structural-check failed"
    return (False, evidence)


def compute_machine_rows(
    task_ids: list[str], granularity_rows: list[dict[str, str]], parse_errors: list[str]
) -> tuple[list[MachineRow], list[str]]:
    rows_by_task: dict[str, dict[str, str]] = {}
    task_issues: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    extra_rows: list[MachineRow] = []
    global_issues = list(parse_errors)

    for row in granularity_rows:
        task = row["task"]
        if task not in task_issues:
            extra_rows.append(
                MachineRow(
                    task=task,
                    total="n/a",
                    verdict="FAIL",
                    trigger="unknown task in draft",
                )
            )
            global_issues.append(f"Granularity Poker references unknown task `{task}`.")
            continue

        if task in rows_by_task:
            task_issues[task].append("duplicate draft row")
            continue

        rows_by_task[task] = row

    machine_rows: list[MachineRow] = []
    blockers: list[str] = []

    for task_id in task_ids:
        row = rows_by_task.get(task_id)
        issues = task_issues[task_id]
        if row is None:
            issues.append("missing draft row")
            machine_rows.append(
                MachineRow(task=task_id, total="n/a", verdict="FAIL", trigger="missing draft row")
            )
            blockers.append(f"Add one granularity poker row for `{task_id}`.")
            continue

        cards: list[int] = []
        for axis in AXES:
            raw_value = row[axis]
            try:
                card = int(raw_value)
            except ValueError:
                issues.append(f"invalid {axis.lower()} card `{raw_value}`")
                continue
            if card not in ALLOWED_CARDS:
                issues.append(f"invalid {axis.lower()} card `{raw_value}`")
                continue
            cards.append(card)

        trigger_parts = list(issues)
        if len(cards) == len(AXES):
            high_axes = [axis for axis in AXES if int(row[axis]) == 8]
            total = sum(cards)
            if high_axes:
                trigger_parts.append(
                    "axis ceiling exceeded (" + ", ".join(axis.lower() for axis in high_axes) + ")"
                )
            if total > 11:
                trigger_parts.append("aggregate score exceeded machine limit")
            verdict = "FAIL" if trigger_parts else "PASS"
            total_text = str(total)
        else:
            verdict = "FAIL"
            total_text = "n/a"

        if verdict == "FAIL":
            blockers.append(f"Re-slice `{task_id}` or fix its granularity poker row.")

        machine_rows.append(
            MachineRow(
                task=task_id,
                total=total_text,
                verdict=verdict,
                trigger="; ".join(trigger_parts) if trigger_parts else "within machine limit",
            )
        )

    machine_rows.extend(extra_rows)
    blockers.extend(global_issues)
    return machine_rows, blockers


def normalize_markdown_section(body: str, fallback: str) -> str:
    return body.strip() if body.strip() else fallback


def build_blocking_issues_section(reviewer_body: str, machine_blockers: list[str]) -> str:
    parts: list[str] = []
    if reviewer_body.strip():
        parts.append(reviewer_body.strip())
    if machine_blockers:
        parts.append("\n".join(f"- [ ] {blocker}" for blocker in machine_blockers))
    if not parts:
        return "- None."
    return "\n\n".join(parts)


def make_decision_reason(
    structural_ok: bool, summary_map: dict[str, str], machine_rows: list[MachineRow]
) -> tuple[str, str]:
    failing_summary = [field for field, verdict in summary_map.items() if verdict == "FAIL"]
    failing_tasks = [row.task for row in machine_rows if row.verdict == "FAIL"]

    if structural_ok and not failing_summary and not failing_tasks:
        return (
            "yes",
            "Structural check passed, all non-granularity viewpoints passed or were N/A, and the machine granularity gate passed.",
        )

    reasons: list[str] = []
    if not structural_ok:
        reasons.append("structural check failed")
    if failing_summary:
        reasons.append("summary failures: " + ", ".join(failing_summary))
    if failing_tasks:
        reasons.append("granularity failures: " + ", ".join(failing_tasks))
    return ("no", "; ".join(reasons))


def render_final_report(
    title: str,
    digest_stamp: str,
    summary_map: dict[str, str],
    structural_ok: bool,
    structural_evidence: str,
    machine_rows: list[MachineRow],
    findings_body: str,
    blocking_body: str,
    improvements_body: str,
    proceed: str,
    reason: str,
) -> str:
    updated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    granularity_verdict = "PASS" if all(row.verdict == "PASS" for row in machine_rows) else "FAIL"
    overall_verdict = "PASS"
    if not structural_ok:
        overall_verdict = "FAIL"
    if any(verdict == "FAIL" for verdict in summary_map.values()):
        overall_verdict = "FAIL"
    if granularity_verdict == "FAIL":
        overall_verdict = "FAIL"

    summary_lines = [
        f"- Forward Fidelity: {summary_map['Forward Fidelity']}",
        f"- Reverse Fidelity: {summary_map['Reverse Fidelity']}",
        f"- Round-trip: {summary_map['Round-trip']}",
        f"- Behavioral Lock: {summary_map['Behavioral Lock']}",
        f"- Negative Path: {summary_map['Negative Path']}",
        f"- Granularity: {granularity_verdict}",
        f"- Temporal: {summary_map['Temporal']}",
        f"- Traceability: {summary_map['Traceability']}",
        f"- Scope: {summary_map['Scope']}",
        f"- Testability: {summary_map['Testability']}",
        f"- Execution Readiness: {summary_map['Execution Readiness']}",
        f"- Integration Coverage: {summary_map['Integration Coverage']}",
        f"- Risk Classification: {summary_map['Risk Classification']}",
        f"- Updated At: {updated_at}",
    ]

    machine_table = "\n".join(
        f"| {row.task} | {row.total} | {row.verdict} | {row.trigger} |" for row in machine_rows
    )

    return "\n".join(
        [
            f"# {title}",
            "",
            "## Review Metadata",
            "",
            digest_stamp,
            f"- **Overall Verdict**: {overall_verdict}",
            "",
            "## Summary",
            "",
            *summary_lines,
            "",
            "## Granularity Gate (Machine)",
            "",
            f"- **Structural Check**: {'PASS' if structural_ok else 'FAIL'}",
            f"- **Structural Evidence**: {structural_evidence or 'not captured'}",
            "",
            "| Task | Total | Verdict | Trigger |",
            "|------|-------|---------|---------|",
            machine_table,
            "",
            "## Findings",
            "",
            findings_body,
            "",
            "## Blocking Issues",
            "",
            blocking_body,
            "",
            "## Non-Blocking Improvements",
            "",
            improvements_body,
            "",
            "## Decision",
            "",
            f"- Proceed to `execute-plan`: {proceed}",
            f"- Reason: {reason}",
            "",
            "Note: This review validates design and plan artifacts only.",
            "Implementation correctness is verified by dod-recheck (L4) and adversarial-verify (L5).",
            "Plan PASS does not imply implementation PASS.",
            "",
        ]
    )


def main() -> int:
    args = parse_args()

    plan_file = Path(args.plan_file).expanduser().resolve()
    draft_file = Path(args.draft_file).expanduser().resolve()
    final_file = Path(args.final_file).expanduser().resolve()

    if not plan_file.is_file():
        raise SystemExit(f"Plan file not found: {plan_file}")
    if not draft_file.is_file():
        raise SystemExit(f"Draft review file not found: {draft_file}")

    plan_text = plan_file.read_text(encoding="utf-8")
    draft_text = draft_file.read_text(encoding="utf-8")
    script_dir = Path(__file__).resolve().parent

    task_ids = parse_plan_tasks(plan_text)
    if not task_ids:
        raise SystemExit("Plan file does not contain any task headings.")

    summary_body = extract_section(draft_text, "Summary") or extract_section(draft_text, "Reviewer Summary")
    summary_map, summary_errors = parse_summary(summary_body)

    granularity_body = extract_section(draft_text, "Granularity Poker")
    granularity_rows, granularity_parse_errors = parse_granularity_table(granularity_body)
    machine_rows, machine_blockers = compute_machine_rows(
        task_ids, granularity_rows, summary_errors + granularity_parse_errors
    )

    findings_body = normalize_markdown_section(
        extract_section(draft_text, "Findings"),
        "\n".join(
            [
                "| ID | Severity | Area | File/Section | Issue | Action |",
                "|----|----------|------|--------------|-------|--------|",
                "| M1 | blocker | review-finalize | draft | Draft omitted the Findings section. | Add reviewer findings and re-run finalization. |",
            ]
        ),
    )
    blocking_body = build_blocking_issues_section(
        extract_section(draft_text, "Blocking Issues"),
        machine_blockers,
    )
    improvements_body = normalize_markdown_section(
        extract_section(draft_text, "Non-Blocking Improvements"),
        "- None.",
    )

    design_file = parse_design_path(plan_text, plan_file)
    structural_ok, structural_evidence = run_structural_check(script_dir, design_file, plan_file)
    if not structural_ok:
        machine_blockers.append("Resolve structural-check failures before rerunning review finalization.")
        blocking_body = build_blocking_issues_section(
            extract_section(draft_text, "Blocking Issues"),
            machine_blockers,
        )

    proceed, reason = make_decision_reason(structural_ok, summary_map, machine_rows)
    digest_stamp = get_digest_stamp(script_dir, plan_file)
    final_text = render_final_report(
        title=parse_plan_title(plan_text, plan_file),
        digest_stamp=digest_stamp,
        summary_map=summary_map,
        structural_ok=structural_ok,
        structural_evidence=structural_evidence.replace("\n", "\\n"),
        machine_rows=machine_rows,
        findings_body=findings_body,
        blocking_body=blocking_body,
        improvements_body=improvements_body,
        proceed=proceed,
        reason=reason,
    )

    final_file.parent.mkdir(parents=True, exist_ok=True)
    final_file.write_text(final_text, encoding="utf-8")
    return 0 if proceed == "yes" else 1


if __name__ == "__main__":
    raise SystemExit(main())
