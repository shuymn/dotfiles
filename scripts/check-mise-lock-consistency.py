#!/usr/bin/env python3
"""Verify that top-level mise tools are locked at the configured versions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    sys.stderr.write("Python 3.11+ with tomllib is required to parse mise TOML\n")
    sys.exit(2)


def load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except Exception as exc:
        sys.stderr.write(f"failed to parse {path}: {exc}\n")
        sys.exit(2)


def config_versions(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, dict) and isinstance(value.get("version"), str):
        return [value["version"]]
    return []


def lock_versions(value: Any) -> list[str]:
    if isinstance(value, list):
        versions = []
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("version"), str):
                versions.append(item["version"])
        return versions
    if isinstance(value, dict) and isinstance(value.get("version"), str):
        return [value["version"]]
    return []


def normalize_version(version: str) -> str:
    if version.startswith("v"):
        return version[1:]
    return version


def check_lock_consistency(config_path: Path, lock_path: Path) -> int:
    config = load_toml(config_path)
    lock = load_toml(lock_path)

    config_tools = config.get("tools", {})
    lock_tools = lock.get("tools", {})
    if not isinstance(config_tools, dict):
        sys.stderr.write(f"{config_path}: [tools] must be a table\n")
        return 2
    if not isinstance(lock_tools, dict):
        sys.stderr.write(f"{lock_path}: [tools] must be a table\n")
        return 2

    failures = []
    checked = 0
    for name, value in config_tools.items():
        expected_versions = config_versions(value)
        if not expected_versions:
            continue
        checked += 1
        if name not in lock_tools:
            failures.append(f"missing lock entry: {name} (expected {', '.join(expected_versions)})")
            continue
        actual_versions = lock_versions(lock_tools[name])
        if not actual_versions:
            failures.append(f"invalid lock entry: {name} (expected {', '.join(expected_versions)})")
            continue

        normalized_actual = {normalize_version(version) for version in actual_versions}
        for expected in expected_versions:
            if normalize_version(expected) not in normalized_actual:
                failures.append(
                    f"version mismatch: {name} config={expected} lock={', '.join(actual_versions)}"
                )

    if checked == 0:
        sys.stderr.write(f"no top-level [tools] entries found in {config_path}\n")
        return 2

    if failures:
        sys.stderr.write("mise lock consistency check failed:\n")
        for failure in failures:
            sys.stderr.write(f"- {failure}\n")
        return 1

    print(f"mise lock consistency check passed ({checked} tools)")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(f"usage: {argv[0]} mise-config.toml mise.lock\n")
        return 2
    return check_lock_consistency(Path(argv[1]), Path(argv[2]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
