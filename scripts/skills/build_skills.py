#!/usr/bin/env python3
"""Build standalone skill artifacts from the source tree."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import deque
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from skills_manifest_refresh import (
    build_manifest,
    discover_skills,
    format_source_root_for_manifest,
)

COMMON_DIR_NAME = "common"
COMMON_DEPENDENCIES_NAME = "dependencies.json"
SKILL_FILE_NAME = "SKILL.md"
SKILL_CONFIG_NAME = "skill.json"
MANIFEST_NAME = ".dotfiles-managed-skills.json"
LOG_PREFIX = "[skills:build]"
SCRIPT_REFERENCE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_./-])(scripts/(?:[A-Za-z0-9][A-Za-z0-9_.-]*/)*[A-Za-z0-9][A-Za-z0-9_.-]*\.[A-Za-z0-9][A-Za-z0-9_.-]*)"
)
TEXT_SUFFIXES = {".md", ".py", ".sh", ".txt", ".json"}
IGNORED_NAMES = {"__pycache__", ".pytest_cache", "tests", SKILL_CONFIG_NAME}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
FORBIDDEN_PATTERNS = ("../_shared", "../../_shared", "../common", "../../common")
EXPLICIT_SKILL_ROOT_PATTERNS = (
    (
        re.compile(r"(?i)\b(?:re-)?run `(?:uv run python |bash )?scripts/"),
        "use <skill-root>/scripts/... for executed helper commands",
    ),
    (
        re.compile(r"(?i)\b(?:read|load|modify|edit|inspect|use) `(?:scripts|references)/"),
        "use <skill-root>/scripts/... or <skill-root>/references/... for skill-relative paths",
    ),
)


class BuildError(RuntimeError):
    """Raised when the generated artifact tree is invalid."""


def log(message: str) -> None:
    print(f"{LOG_PREFIX} {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build standalone skill artifacts")
    parser.add_argument("--source", required=True, help="Path to the source skills root")
    parser.add_argument("--artifact", required=True, help="Path to the artifact skills root")
    return parser.parse_args()


def should_ignore(name: str) -> bool:
    return name in IGNORED_NAMES or Path(name).suffix in IGNORED_SUFFIXES


def ignore_source_entries(_dir: str, names: list[str]) -> set[str]:
    return {name for name in names if should_ignore(name)}


def is_skill_dir(path: Path) -> bool:
    return path.is_dir() and (path / SKILL_FILE_NAME).is_file()


def iter_skill_dirs(source_root: Path) -> list[Path]:
    return [
        child
        for child in sorted(source_root.iterdir())
        if child.name != COMMON_DIR_NAME and is_skill_dir(child)
    ]


def clean_artifact_root(artifact_root: Path) -> None:
    if artifact_root.exists():
        shutil.rmtree(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)


def write_manifest(artifact_root: Path) -> None:
    manifest_path = artifact_root / MANIFEST_NAME
    manifest_source_root = format_source_root_for_manifest(artifact_root, manifest_path)
    manifest = build_manifest(manifest_source_root, discover_skills(artifact_root))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def iter_text_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and (path.suffix in TEXT_SUFFIXES or path.name == SKILL_FILE_NAME)
    ]


def load_common_dependency_graph(source_root: Path) -> dict[str, tuple[str, ...]]:
    path = source_root / COMMON_DIR_NAME / COMMON_DEPENDENCIES_NAME
    if not path.is_file():
        raise BuildError(f"common dependency config not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BuildError("common dependency config must be an object")

    graph: dict[str, tuple[str, ...]] = {}
    common_scripts_root = source_root / COMMON_DIR_NAME / "scripts"
    for script_name, dependencies in payload.items():
        if not isinstance(script_name, str) or not isinstance(dependencies, list):
            raise BuildError("common dependency config entries must map strings to arrays")
        script_path = common_scripts_root / script_name
        if not script_path.is_file():
            raise BuildError(f"common dependency config references missing script: {script_path}")
        graph[script_name] = tuple(
            dependency for dependency in dependencies if isinstance(dependency, str)
        )

    for script_name, dependencies in graph.items():
        for dependency in dependencies:
            if dependency not in graph:
                raise BuildError(
                    f"common dependency config references unknown dependency: {script_name} -> {dependency}"
                )

    return graph


def load_skill_common_scripts(skill_root: Path) -> tuple[str, ...]:
    config_path = skill_root / SKILL_CONFIG_NAME
    if not config_path.is_file():
        return ()

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    scripts = payload.get("common_scripts")
    if not isinstance(scripts, list):
        raise BuildError(f"{skill_root.name}: skill.json common_scripts must be an array")

    result = [item for item in scripts if isinstance(item, str)]
    if len(result) != len(scripts):
        raise BuildError(f"{skill_root.name}: skill.json common_scripts must contain only strings")
    return tuple(result)


def resolve_common_scripts(
    common_graph: dict[str, tuple[str, ...]], requested_scripts: tuple[str, ...], skill_name: str
) -> tuple[str, ...]:
    resolved: list[str] = []
    seen: set[str] = set()
    queue = deque(requested_scripts)

    while queue:
        script_name = queue.popleft()
        if script_name in seen:
            continue
        if script_name not in common_graph:
            raise BuildError(f"{skill_name}: unknown common script dependency `{script_name}`")
        seen.add(script_name)
        resolved.append(script_name)
        queue.extend(common_graph[script_name])

    return tuple(sorted(resolved))


def validate_referenced_scripts(skill_root: Path, available_common_scripts: tuple[str, ...] = ()) -> None:
    skill_md = skill_root / SKILL_FILE_NAME
    contents = skill_md.read_text(encoding="utf-8")
    referenced = sorted(set(SCRIPT_REFERENCE_PATTERN.findall(contents)))
    missing: list[str] = []
    not_executable: list[str] = []
    common_script_names = set(available_common_scripts)

    for reference in referenced:
        script_path = skill_root / reference
        if not script_path.is_file() and Path(reference).parent.as_posix() == "scripts":
            if Path(reference).name in common_script_names:
                continue
        if not script_path.is_file():
            missing.append(reference)
            continue
        if script_path.suffix == ".sh" and not os.access(script_path, os.X_OK):
            not_executable.append(reference)

    if missing:
        raise BuildError(
            f"{skill_root.name}: missing scripts referenced by SKILL.md: {', '.join(missing)}"
        )
    if not_executable:
        raise BuildError(
            f"{skill_root.name}: shell scripts must be executable: {', '.join(not_executable)}"
        )


def validate_no_forbidden_paths(skill_root: Path) -> None:
    violations: list[str] = []
    for path in iter_text_files(skill_root):
        contents = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in contents:
                violations.append(f"{path.relative_to(skill_root)}:{pattern}")
    if violations:
        raise BuildError(
            f"{skill_root.name}: forbidden path traversal references remain: {', '.join(violations)}"
        )


def validate_explicit_skill_root_paths(skill_root: Path) -> None:
    violations: list[str] = []
    for path in sorted(skill_root.rglob("*.md")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern, hint in EXPLICIT_SKILL_ROOT_PATTERNS:
                if pattern.search(line):
                    relative = path.relative_to(skill_root).as_posix()
                    violations.append(f"{relative}:{lineno} ({hint})")
                    break
    if violations:
        raise BuildError(
            f"{skill_root.name}: bare skill-relative path references remain: {', '.join(violations)}"
        )


def validate_artifact_root(artifact_root: Path) -> None:
    leaked_paths = [
        str(path.relative_to(artifact_root))
        for path in sorted(artifact_root.rglob("*"))
        if path.name in IGNORED_NAMES or path.suffix in IGNORED_SUFFIXES
    ]
    if leaked_paths:
        raise BuildError(
            "artifact tree contains source-only files: " + ", ".join(leaked_paths)
        )

    for skill_root in iter_skill_dirs(artifact_root):
        validate_referenced_scripts(skill_root)
        validate_no_forbidden_paths(skill_root)
        validate_explicit_skill_root_paths(skill_root)


def copy_common_scripts(
    source_root: Path, artifact_skill_root: Path, resolved_common_scripts: tuple[str, ...]
) -> None:
    if not resolved_common_scripts:
        return

    scripts_root = artifact_skill_root / "scripts"
    scripts_root.mkdir(parents=True, exist_ok=True)
    common_scripts_root = source_root / COMMON_DIR_NAME / "scripts"
    for script_name in resolved_common_scripts:
        shutil.copy2(common_scripts_root / script_name, scripts_root / script_name)


def copy_skill(
    source_root: Path,
    source_skill_root: Path,
    artifact_root: Path,
    common_graph: dict[str, tuple[str, ...]],
) -> None:
    artifact_skill_root = artifact_root / source_skill_root.name
    shutil.copytree(
        source_skill_root,
        artifact_skill_root,
        copy_function=shutil.copy2,
        ignore=ignore_source_entries,
    )
    requested_common_scripts = load_skill_common_scripts(source_skill_root)
    resolved_common_scripts = resolve_common_scripts(
        common_graph, requested_common_scripts, source_skill_root.name
    )
    copy_common_scripts(source_root, artifact_skill_root, resolved_common_scripts)


def build_skills(source_root: Path, artifact_root: Path) -> None:
    source_root = source_root.expanduser().resolve()
    artifact_root = artifact_root.expanduser().resolve()

    if source_root == artifact_root:
        raise BuildError("source and artifact roots must be different")
    if not source_root.is_dir():
        raise BuildError(f"source skills directory does not exist: {source_root}")
    if not (source_root / COMMON_DIR_NAME / "scripts").is_dir():
        raise BuildError(f"common scripts directory does not exist: {source_root / COMMON_DIR_NAME / 'scripts'}")
    common_graph = load_common_dependency_graph(source_root)

    for source_skill_root in iter_skill_dirs(source_root):
        requested_common_scripts = load_skill_common_scripts(source_skill_root)
        resolved_common_scripts = resolve_common_scripts(
            common_graph, requested_common_scripts, source_skill_root.name
        )
        validate_referenced_scripts(source_skill_root, resolved_common_scripts)
        validate_no_forbidden_paths(source_skill_root)
        validate_explicit_skill_root_paths(source_skill_root)

    clean_artifact_root(artifact_root)

    for source_skill_root in iter_skill_dirs(source_root):
        copy_skill(source_root, source_skill_root, artifact_root, common_graph)

    write_manifest(artifact_root)
    validate_artifact_root(artifact_root)

    log(f"source={source_root}")
    log(f"artifact={artifact_root}")
    log(f"skills={len(iter_skill_dirs(artifact_root))}")


def main() -> int:
    args = parse_args()
    build_skills(Path(args.source), Path(args.artifact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
