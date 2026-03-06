#!/usr/bin/env python3
"""Check that all [required] attack vectors within selected categories are covered.

Usage:
  uv run python adversarial_coverage_check.py <report.md> <attack-vectors.md> --tier <tier>

  tier: Critical | Sensitive | Standard

For Critical/Sensitive: every [required] vector in each selected category must be:
  (a) executed as a probe, or (b) documented as non-applicable with rationale.
  Uncovered [required] vectors without documented N/A rationale → FAIL.

For Standard: no [required] coverage obligation → SKIP.

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

TOOL_NAME = "adversarial-coverage-check"

_REQUIRED_TAG_RE = re.compile(r"\[required\]", re.IGNORECASE)
_CATEGORY_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+(.+)$", re.MULTILINE)
_NA_SIGNAL_RE = re.compile(
    r"\b(?:n[/\\]a|non[- ]?applicable|not applicable|inapplicable)\b",
    re.IGNORECASE,
)


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().casefold())


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
    for line in lines[2:]:  # skip separator
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def parse_attack_vectors(text: str) -> dict[str, list[tuple[str, bool]]]:
    """Parse attack-vectors.md. Returns {category_name: [(vector_name, is_required)]}."""
    result: dict[str, list[tuple[str, bool]]] = {}
    sections = list(_CATEGORY_HEADING_RE.finditer(text))
    for i, m in enumerate(sections):
        cat = m.group(2).strip()
        start = m.end()
        end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        section_text = text[start:end]
        vectors: list[tuple[str, bool]] = []
        for vm in re.finditer(
            r"^-\s+\*\*([^*]+)\*\*(?:\s+\[required\])?[^:]*:",
            section_text,
            re.MULTILINE,
        ):
            name = vm.group(1).strip()
            line_end = section_text.find("\n", vm.start())
            line = section_text[vm.start(): (line_end if line_end >= 0 else len(section_text))]
            is_required = bool(_REQUIRED_TAG_RE.search(line))
            vectors.append((name, is_required))
        if vectors:
            result[cat] = vectors
    return result


def parse_attack_summary(report_text: str) -> list[dict[str, str]]:
    section = _extract_section(report_text, "Attack Summary")
    return _parse_table(section) if section else []


def parse_selected_categories(
    report_text: str, known_cats: dict[str, list]
) -> list[str]:
    """Infer selected categories from Attack Summary Category column."""
    summary_rows = parse_attack_summary(report_text)
    found: list[str] = []
    seen: set[str] = set()

    for row in summary_rows:
        cat_text = _normalize(row.get("Category", ""))
        for cat_name in known_cats:
            cat_norm = _normalize(cat_name)
            # Match on partial overlap (category number prefix or keyword)
            if cat_norm in cat_text or cat_text in cat_norm:
                if cat_name not in seen:
                    seen.add(cat_name)
                    found.append(cat_name)
                break

    # Also look for explicit category selection section in the report
    section_pattern = re.compile(
        r"(?ms)(?:Selected(?:\s+Attack)?\s+Categor(?:y|ies)|Attack\s+Categor(?:y|ies))\s*:?\s*\n(.*?)(?=^##|\Z)"
    )
    m = section_pattern.search(report_text)
    if m:
        for line in m.group(1).splitlines():
            stripped = line.strip().lstrip("-* ")
            for cat_name in known_cats:
                if _normalize(cat_name) in _normalize(stripped):
                    if cat_name not in seen:
                        seen.add(cat_name)
                        found.append(cat_name)

    return found


def _is_covered(
    vector_name: str,
    covered_vectors: set[str],
    na_vectors: set[str],
) -> bool:
    norm = _normalize(vector_name)
    for candidate in covered_vectors | na_vectors:
        # Allow partial match for minor naming variations
        if norm in candidate or candidate in norm:
            return True
    return False


def check_coverage(
    selected: list[str],
    attack_vectors: dict[str, list[tuple[str, bool]]],
    summary_rows: list[dict[str, str]],
    tier: str,
) -> list[str]:
    """Return issues list. Only Critical/Sensitive have [required] coverage obligations."""
    if tier == "Standard":
        return []

    covered: set[str] = set()
    na_covered: set[str] = set()

    for row in summary_rows:
        vec_name = _normalize(row.get("Attack Vector", ""))
        result = row.get("Result", "")
        evidence = row.get("Evidence", "")
        if vec_name:
            covered.add(vec_name)
            if _NA_SIGNAL_RE.search(result) or _NA_SIGNAL_RE.search(evidence):
                na_covered.add(vec_name)

    issues: list[str] = []
    for cat in selected:
        vectors = attack_vectors.get(cat, [])
        required_vectors = [name for name, req in vectors if req]
        for vec_name in required_vectors:
            if not _is_covered(vec_name, covered, na_covered):
                issues.append(
                    f"[required] vector not covered in {cat!r}: {vec_name!r}"
                    " — execute a probe or document non-applicability with rationale"
                )
    return issues


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Adversarial required vector coverage check")
    parser.add_argument("report_file", help="Path to adversarial report .md")
    parser.add_argument("attack_vectors_file", help="Path to attack-vectors.md")
    parser.add_argument(
        "--tier",
        required=True,
        choices=["Critical", "Sensitive", "Standard"],
        help="Risk tier of the task",
    )
    args = parser.parse_args(argv[1:])

    mode = resolve_mode()
    report_path = Path(args.report_file)
    vectors_path = Path(args.attack_vectors_file)

    for label, path in (("Report", report_path), ("Attack vectors", vectors_path)):
        if not path.exists():
            code = label.upper().replace(" ", "_") + "_FILE_NOT_FOUND"
            emit_header(TOOL_NAME, mode, "FAIL", code, f"{label} file not found: {path}")
            emit_line("fix.1", "FIX_FILE_PATH")
            emit_footer()
            return 1

    if args.tier == "Standard":
        emit_header(
            TOOL_NAME, mode, "SKIP", "STANDARD_TIER_NO_REQUIRED_COVERAGE",
            "Standard tier: no [required] vector coverage obligation.",
        )
        emit_footer()
        return 0

    report_text = report_path.read_text(encoding="utf-8")
    vectors_text = vectors_path.read_text(encoding="utf-8")

    attack_vectors = parse_attack_vectors(vectors_text)
    summary_rows = parse_attack_summary(report_text)
    selected = parse_selected_categories(report_text, attack_vectors)

    if not selected:
        emit_header(
            TOOL_NAME, mode, "SKIP", "NO_SELECTED_CATEGORIES",
            "Could not determine selected attack categories from Attack Summary.",
        )
        emit_footer()
        return 0

    issues = check_coverage(selected, attack_vectors, summary_rows, args.tier)

    overall = "FAIL" if issues else "PASS"
    code = "REQUIRED_VECTORS_NOT_COVERED" if issues else "ALL_REQUIRED_VECTORS_COVERED"
    summary = (
        f"{len(issues)} [required] vector(s) uncovered for tier={args.tier}."
        if issues
        else (
            f"All [required] vectors covered across {len(selected)} selected"
            f" categories (tier={args.tier})."
        )
    )

    emit_header(TOOL_NAME, mode, overall, code, summary)
    emit_line("signal.tier", args.tier)
    emit_line("signal.selected_categories", len(selected))
    emit_line("signal.issues", len(issues))

    for cat in selected:
        emit_line("category", cat)
    for i, issue in enumerate(issues, 1):
        emit_line(f"issue.{i}", issue)

    if issues:
        emit_line("fix.1", "FIX_ADD_MISSING_PROBE_OR_DOCUMENT_NA_RATIONALE")

    emit_footer()
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
