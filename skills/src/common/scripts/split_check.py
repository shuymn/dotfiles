#!/usr/bin/env python3
"""Validate single/root-sub split decisions from structured design signals."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

OUTPUT_SCHEMA = "LLM_CHECK_V2"
TOOL_NAME = "split-check"

REQUIRED_BOUNDARY_COLUMNS = [
    "Boundary",
    "Owns Requirements/AC",
    "Primary Verification Surface",
    "TEMP Lifecycle Group",
    "Parallel Stream",
    "Depends On",
]
REQUIRED_SUBDOC_INDEX_COLUMNS = [
    "Sub ID",
    "File",
    "Owned Boundary",
    "Owns Requirements/AC",
]
NONE_TOKENS = {"", "-", "none", "n/a", "na"}
TRUE_TOKENS = {"yes", "true", "y"}
INTEGRATION_ONLY_TOKEN = "integration-only"


@dataclass(frozen=True)
class BoundaryRow:
    boundary: str
    owns_requirements: str
    verification_surface: str
    temp_lifecycle_group: str
    parallel_stream: str
    depends_on: tuple[str, ...]

    @property
    def normalized_boundary(self) -> str:
        return normalize_token(self.boundary)

    @property
    def is_owned(self) -> bool:
        owns = normalize_token(self.owns_requirements)
        return owns not in NONE_TOKENS and owns != INTEGRATION_ONLY_TOKEN

    @property
    def is_parallel(self) -> bool:
        return normalize_token(self.parallel_stream) in TRUE_TOKENS


@dataclass(frozen=True)
class SubDocIndexRow:
    sub_id: str
    file: str
    owned_boundary: str
    owns_requirements: str

    @property
    def normalized_boundary(self) -> str:
        return normalize_token(self.owned_boundary)


@dataclass(frozen=True)
class SubDocInfo:
    path: Path
    owned_boundary: str
    local_requirement_count: int
    local_ac_count: int
    errors: tuple[str, ...] = ()

    @property
    def normalized_boundary(self) -> str:
        return normalize_token(self.owned_boundary)

    @property
    def is_effective(self) -> bool:
        return self.local_requirement_count > 0 and self.local_ac_count > 0


@dataclass
class DesignDocData:
    design_file: Path
    split_decision: str = ""
    boundary_rows: list[BoundaryRow] = field(default_factory=list)
    subdoc_index_rows: list[SubDocIndexRow] = field(default_factory=list)
    subdocs: list[SubDocInfo] = field(default_factory=list)
    root_acceptance_count: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    status: str
    code: str
    summary: str
    blockers: list[str]
    advisories: list[str]
    signals: dict[str, str]
    split_decision: str
    design_file: Path


def normalize_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_token(value))
    return slug.strip("-") or "unknown"


def extract_section(text: str, title: str, level: int = 2) -> str:
    hashes = "#" * level
    pattern = re.compile(
        rf"(?ms)^{re.escape(hashes)}\s+{re.escape(title)}\s*$\n(.*?)(?=^#{{1,{level}}}\s+|\Z)"
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def extract_table_block(text: str) -> list[str]:
    lines = text.splitlines()
    table_lines: list[str] = []
    in_table = False
    for line in lines:
        if line.lstrip().startswith("|"):
            table_lines.append(line.strip())
            in_table = True
            continue
        if in_table:
            break
    return table_lines


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_separator_row(parts: list[str]) -> bool:
    if not parts:
        return False
    return all(re.fullmatch(r":?-{3,}:?", part or "") for part in parts)


def parse_markdown_table(text: str) -> tuple[list[str], list[dict[str, str]]]:
    lines = extract_table_block(text)
    if len(lines) < 2:
        return [], []

    headers = split_markdown_row(lines[0])
    if not headers:
        return [], []

    data_start = 1
    separator = split_markdown_row(lines[1])
    if len(separator) == len(headers) and is_separator_row(separator):
        data_start = 2

    rows: list[dict[str, str]] = []
    for line in lines[data_start:]:
        parts = split_markdown_row(line)
        if len(parts) != len(headers):
            continue
        rows.append(dict(zip(headers, parts, strict=True)))
    return headers, rows


def parse_key_value_bullets(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r"^-\s*([^:]+):\s*(.+)$", line)
        if match:
            result[match.group(1).strip()] = match.group(2).strip()
    return result


def count_bullet_items(text: str) -> int:
    count = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("<!--"):
            continue
        if re.match(r"^-\s+\S+", line):
            count += 1
    return count


def parse_dependencies(value: str) -> tuple[str, ...]:
    if normalize_token(value) in NONE_TOKENS:
        return ()
    parts = [part.strip() for part in re.split(r"[;,]", value) if part.strip()]
    return tuple(parts)


def resolve_repo_relative_path(design_file: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return candidate

    search_roots = [design_file.parent, *design_file.parents]
    seen: set[Path] = set()
    for root in search_roots:
        if root in seen:
            continue
        seen.add(root)
        path = root / candidate
        if path.exists():
            return path
    return Path.cwd() / candidate


def parse_subdoc(path: Path) -> SubDocInfo:
    if not path.exists():
        return SubDocInfo(
            path=path,
            owned_boundary="",
            local_requirement_count=0,
            local_ac_count=0,
            errors=(f"Sub-doc file is missing: `{path.as_posix()}`.",),
        )

    text = path.read_text(encoding="utf-8")
    metadata = parse_key_value_bullets(extract_section(text, "Sub-Doc Metadata"))
    local_requirements = count_bullet_items(extract_section(text, "Local Requirements"))
    _headers, local_ac_rows = parse_markdown_table(
        extract_section(text, "Local Acceptance Criteria")
    )
    errors: list[str] = []
    owned_boundary = metadata.get("Owned Boundary", "")
    if not owned_boundary:
        errors.append(
            f"Sub-doc `{path.as_posix()}` is missing `Owned Boundary` metadata."
        )
    return SubDocInfo(
        path=path,
        owned_boundary=owned_boundary,
        local_requirement_count=local_requirements,
        local_ac_count=len(local_ac_rows),
        errors=tuple(errors),
    )


def parse_design_doc(design_file: Path) -> DesignDocData:
    text = design_file.read_text(encoding="utf-8")
    data = DesignDocData(design_file=design_file)

    decomposition_section = extract_section(text, "Decomposition Strategy")
    if not decomposition_section:
        data.errors.append("Design doc is missing `## Decomposition Strategy`.")
        return data

    fields = parse_key_value_bullets(decomposition_section)
    data.split_decision = normalize_token(fields.get("Split Decision", ""))
    if data.split_decision not in {"single", "root-sub"}:
        data.errors.append("`Split Decision` must be `single` or `root-sub`.")

    boundary_section = extract_section(
        decomposition_section, "Boundary Inventory", level=3
    )
    if not boundary_section:
        data.errors.append(
            "`## Decomposition Strategy` must include `### Boundary Inventory`."
        )
    else:
        headers, rows = parse_markdown_table(boundary_section)
        if headers != REQUIRED_BOUNDARY_COLUMNS:
            data.errors.append(
                "`### Boundary Inventory` must use columns: "
                + ", ".join(f"`{column}`" for column in REQUIRED_BOUNDARY_COLUMNS)
                + "."
            )
        seen_boundaries: dict[str, str] = {}
        for row in rows:
            boundary = row.get("Boundary", "").strip()
            if not boundary:
                data.errors.append(
                    "Boundary Inventory contains a row with an empty `Boundary` value."
                )
                continue
            normalized_boundary = normalize_token(boundary)
            if normalized_boundary in seen_boundaries:
                data.errors.append(
                    f"Boundary Inventory repeats boundary `{boundary}` "
                    f"(already used by `{seen_boundaries[normalized_boundary]}`)."
                )
                continue
            seen_boundaries[normalized_boundary] = boundary
            data.boundary_rows.append(
                BoundaryRow(
                    boundary=boundary,
                    owns_requirements=row.get("Owns Requirements/AC", "").strip(),
                    verification_surface=row.get(
                        "Primary Verification Surface", ""
                    ).strip(),
                    temp_lifecycle_group=row.get("TEMP Lifecycle Group", "").strip(),
                    parallel_stream=row.get("Parallel Stream", "").strip(),
                    depends_on=parse_dependencies(row.get("Depends On", "")),
                )
            )

    _headers, acceptance_rows = parse_markdown_table(
        extract_section(text, "Acceptance Criteria")
    )
    data.root_acceptance_count = len(acceptance_rows)

    if data.split_decision != "root-sub":
        return data

    subdoc_section = extract_section(decomposition_section, "Sub-Doc Index", level=3)
    if not subdoc_section:
        data.errors.append("`Split Decision: root-sub` requires `### Sub-Doc Index`.")
        return data

    headers, rows = parse_markdown_table(subdoc_section)
    if headers != REQUIRED_SUBDOC_INDEX_COLUMNS:
        data.errors.append(
            "`### Sub-Doc Index` must use columns: "
            + ", ".join(f"`{column}`" for column in REQUIRED_SUBDOC_INDEX_COLUMNS)
            + "."
        )

    seen_subdoc_boundaries: dict[str, str] = {}
    for row in rows:
        sub_id = row.get("Sub ID", "").strip()
        file_value = row.get("File", "").strip()
        owned_boundary = row.get("Owned Boundary", "").strip()
        owns_requirements = row.get("Owns Requirements/AC", "").strip()
        if not sub_id or not file_value or not owned_boundary:
            data.errors.append(
                "Sub-Doc Index rows must populate `Sub ID`, `File`, and `Owned Boundary`."
            )
            continue
        normalized_boundary = normalize_token(owned_boundary)
        if normalized_boundary in seen_subdoc_boundaries:
            data.errors.append(
                f"Sub-Doc Index repeats owned boundary `{owned_boundary}` "
                f"(already used by `{seen_subdoc_boundaries[normalized_boundary]}`)."
            )
        else:
            seen_subdoc_boundaries[normalized_boundary] = sub_id
        row_data = SubDocIndexRow(
            sub_id=sub_id,
            file=file_value,
            owned_boundary=owned_boundary,
            owns_requirements=owns_requirements,
        )
        data.subdoc_index_rows.append(row_data)
        subdoc_path = resolve_repo_relative_path(design_file, file_value)
        subdoc = parse_subdoc(subdoc_path)
        if subdoc.errors:
            data.errors.extend(subdoc.errors)
        if (
            subdoc.owned_boundary
            and subdoc.normalized_boundary != row_data.normalized_boundary
        ):
            data.errors.append(
                f"Sub-doc `{file_value}` declares owned boundary `{subdoc.owned_boundary}`, "
                f"but Sub-Doc Index maps it to `{owned_boundary}`."
            )
        data.subdocs.append(subdoc)

    return data


def build_signals(data: DesignDocData) -> dict[str, str]:
    owned_boundaries = [row for row in data.boundary_rows if row.is_owned]
    known_boundaries = {row.normalized_boundary for row in data.boundary_rows}
    verification_surfaces = {
        normalize_token(row.verification_surface)
        for row in owned_boundaries
        if normalize_token(row.verification_surface) not in NONE_TOKENS
    }
    temp_groups = {
        normalize_token(row.temp_lifecycle_group)
        for row in owned_boundaries
        if normalize_token(row.temp_lifecycle_group) not in NONE_TOKENS
    }
    dependency_edges = {
        (row.normalized_boundary, normalize_token(dependency))
        for row in owned_boundaries
        for dependency in row.depends_on
        if normalize_token(dependency) in known_boundaries
        and normalize_token(dependency) != row.normalized_boundary
    }
    effective_subdocs = [subdoc for subdoc in data.subdocs if subdoc.is_effective]
    local_ac_distribution: dict[str, int] = {}
    for row, subdoc in zip(data.subdoc_index_rows, data.subdocs, strict=True):
        boundary_name = subdoc.owned_boundary or row.owned_boundary or row.sub_id
        local_ac_distribution[boundary_name] = subdoc.local_ac_count

    signals: dict[str, str] = {
        "owned_boundary_count": str(len(owned_boundaries)),
        "verification_surface_count": str(len(verification_surfaces)),
        "temp_lifecycle_group_count": str(len(temp_groups)),
        "parallelizable_boundary_count": str(
            sum(1 for row in owned_boundaries if row.is_parallel)
        ),
        "dependency_edge_count": str(len(dependency_edges)),
        "effective_subdoc_count": str(len(effective_subdocs)),
        "root_integration_ac_count": str(data.root_acceptance_count),
        "local_ac_total": str(sum(local_ac_distribution.values())),
    }
    for boundary, count in sorted(
        local_ac_distribution.items(), key=lambda item: slugify(item[0])
    ):
        signals[f"local_ac.{slugify(boundary)}"] = str(count)
    return signals


def analyze_design_doc(data: DesignDocData) -> CheckResult:
    blockers = list(data.errors)
    advisories: list[str] = []
    signals = build_signals(data)

    owned_boundary_count = int(signals["owned_boundary_count"])
    verification_surface_count = int(signals["verification_surface_count"])
    temp_group_count = int(signals["temp_lifecycle_group_count"])
    parallelizable_boundary_count = int(signals["parallelizable_boundary_count"])
    dependency_edge_count = int(signals["dependency_edge_count"])
    effective_subdoc_count = int(signals["effective_subdoc_count"])
    root_integration_ac_count = int(signals["root_integration_ac_count"])
    local_ac_total = int(signals["local_ac_total"])

    if owned_boundary_count == 0:
        blockers.append(
            "Boundary Inventory must include at least one boundary that owns requirements/AC."
        )

    if data.split_decision == "single":
        triggers: list[str] = []
        if verification_surface_count >= 2:
            triggers.append(f"{verification_surface_count} verification surfaces")
        if temp_group_count >= 2:
            triggers.append(f"{temp_group_count} TEMP lifecycle groups")
        if parallelizable_boundary_count >= 2:
            triggers.append(f"{parallelizable_boundary_count} parallel streams")
        if owned_boundary_count >= 2 and triggers:
            blockers.append(
                "`Split Decision: single` is inconsistent with Boundary Inventory: "
                f"{owned_boundary_count} owned boundaries and "
                + ", ".join(triggers)
                + "."
            )

    if data.split_decision == "root-sub":
        inventory_boundaries = {
            row.normalized_boundary: row.boundary
            for row in data.boundary_rows
            if row.is_owned
        }
        index_boundaries = {
            row.normalized_boundary: row.owned_boundary
            for row in data.subdoc_index_rows
        }
        missing_in_index = [
            boundary
            for boundary in inventory_boundaries
            if boundary not in index_boundaries
        ]
        extra_in_index = [
            boundary
            for boundary in index_boundaries
            if boundary not in inventory_boundaries
        ]
        if missing_in_index or extra_in_index:
            messages: list[str] = []
            if missing_in_index:
                messages.append(
                    "missing in Sub-Doc Index: "
                    + ", ".join(
                        f"`{inventory_boundaries[item]}`" for item in missing_in_index
                    )
                )
            if extra_in_index:
                messages.append(
                    "extra in Sub-Doc Index: "
                    + ", ".join(
                        f"`{index_boundaries[item]}`" for item in extra_in_index
                    )
                )
            blockers.append(
                "Boundary Inventory and Sub-Doc Index must match 1:1 for sub-owned boundaries ("
                + "; ".join(messages)
                + ")."
            )
        if effective_subdoc_count < 2:
            blockers.append(
                "`Split Decision: root-sub` requires at least 2 effective sub-docs with both "
                "Local Requirements and Local Acceptance Criteria."
            )

        if local_ac_total > 0:
            distribution = [
                (boundary, count)
                for boundary, count in (
                    (
                        subdoc.owned_boundary or row.owned_boundary or row.sub_id,
                        subdoc.local_ac_count,
                    )
                    for row, subdoc in zip(
                        data.subdoc_index_rows, data.subdocs, strict=True
                    )
                )
            ]
            largest_boundary, largest_count = max(
                distribution, key=lambda item: item[1], default=("", 0)
            )
            if largest_count / local_ac_total > 0.70:
                advisories.append(
                    f"Local ACs are concentrated in `{largest_boundary}` ({largest_count}/{local_ac_total}); "
                    "root-sub may still be too coarse."
                )
        if local_ac_total > 0 and root_integration_ac_count >= local_ac_total:
            advisories.append(
                "Root integration AC count is greater than or equal to total local AC count; "
                "integration scope may be dominating the split."
            )
        if owned_boundary_count > 0 and dependency_edge_count > owned_boundary_count:
            advisories.append(
                "Cross-boundary dependency edges exceed owned boundary count; "
                "the split may be too tightly coupled."
            )

    if blockers:
        return CheckResult(
            status="FAIL",
            code="SPLIT_CONFLICT",
            summary="Split decision blockers found.",
            blockers=blockers,
            advisories=advisories,
            signals=signals,
            split_decision=data.split_decision or "unknown",
            design_file=data.design_file,
        )

    summary = "Split decision signals are consistent."
    if advisories:
        summary = "Split decision passes with advisories."
    return CheckResult(
        status="PASS",
        code="PASS",
        summary=summary,
        blockers=[],
        advisories=advisories,
        signals=signals,
        split_decision=data.split_decision or "unknown",
        design_file=data.design_file,
    )


def emit_result(result: CheckResult, mode: str) -> int:
    print(OUTPUT_SCHEMA)
    print(f"tool={TOOL_NAME}")
    print(f"mode={mode}")
    print(f"status={result.status}")
    print(f"code={result.code}")
    print(f"summary={sanitize(result.summary)}")
    print(f"input.design_file={sanitize(result.design_file.as_posix())}")
    print(f"split_decision={sanitize(result.split_decision)}")
    for key, value in result.signals.items():
        print(f"signal.{key}={sanitize(value)}")
    print(f"advisory.count={len(result.advisories)}")
    for index, advisory in enumerate(result.advisories, start=1):
        print(f"advisory.{index}={sanitize(advisory)}")
    print(f"blocker.count={len(result.blockers)}")
    for index, blocker in enumerate(result.blockers, start=1):
        print(f"blocker.{index}={sanitize(blocker)}")
    print(f"END_{OUTPUT_SCHEMA}")
    return 0 if result.status == "PASS" else 1


def sanitize(value: str) -> str:
    return value.replace("\r", "").replace("\n", "\\n")


def emit_cli_error(mode: str, code: str, summary: str) -> int:
    print(OUTPUT_SCHEMA)
    print(f"tool={TOOL_NAME}")
    print(f"mode={mode}")
    print("status=FAIL")
    print(f"code={code}")
    print(f"summary={sanitize(summary)}")
    print("advisory.count=0")
    print("blocker.count=1")
    print(f"blocker.1={sanitize(summary)}")
    print(f"END_{OUTPUT_SCHEMA}")
    return 1


def main(argv: list[str]) -> int:
    mode = normalize_token(os.environ.get("LLM_CHECK_MODE", "compact"))
    if mode not in {"compact", "full"}:
        mode = "compact"

    if len(argv) != 2:
        return emit_cli_error(
            mode, "INVALID_ARGUMENT_COUNT", "Usage: split_check.py <design-file>."
        )

    design_file = Path(argv[1]).resolve()
    if not design_file.exists():
        return emit_cli_error(
            mode, "DESIGN_FILE_NOT_FOUND", f"Design file not found: `{design_file}`."
        )

    data = parse_design_doc(design_file)
    result = analyze_design_doc(data)
    return emit_result(result, mode)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
