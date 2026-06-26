#!/usr/bin/env python3
"""Verify that top-level mise tools are locked at the configured versions.

For configured HTTP tools, also verify that lockfile platform URLs and persisted
lock options still match the config shape Renovate should regenerate.
"""

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


def lock_entries(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def lock_versions(value: Any) -> list[str]:
    return [
        entry["version"] for entry in lock_entries(value) if isinstance(entry.get("version"), str)
    ]


def normalize_version(version: str) -> str:
    if version.startswith("v"):
        return version[1:]
    return version


def lockfile_platforms(config: dict[str, Any]) -> list[str]:
    settings = config.get("settings", {})
    if not isinstance(settings, dict):
        return []
    platforms = settings.get("lockfile_platforms", [])
    if not isinstance(platforms, list):
        return []
    return [platform for platform in platforms if isinstance(platform, str)]


def is_http_url_tool(name: str, value: Any) -> bool:
    return name.startswith("http:") and isinstance(value, dict) and isinstance(value.get("url"), str)


def config_lock_options(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    config_only_keys = {"version", "url", "bin"}
    return {key: option for key, option in value.items() if key not in config_only_keys}


def option_string(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def lock_platform(entry: dict[str, Any], platform: str) -> dict[str, Any] | None:
    nested_platforms = entry.get("platforms")
    if isinstance(nested_platforms, dict):
        nested_platform = nested_platforms.get(platform)
        if isinstance(nested_platform, dict):
            return nested_platform

    dotted_platform = entry.get(f"platforms.{platform}")
    if isinstance(dotted_platform, dict):
        return dotted_platform

    return None


def check_url_tool_lock(
    name: str,
    config_value: Any,
    lock_value: Any,
    expected_versions: list[str],
    platforms: list[str],
) -> list[str]:
    if not is_http_url_tool(name, config_value):
        return []

    failures = []
    entries = lock_entries(lock_value)
    expected_options = config_lock_options(config_value)
    config_url = config_value["url"]

    for expected in expected_versions:
        matching_entries = [
            entry
            for entry in entries
            if isinstance(entry.get("version"), str)
            and normalize_version(entry["version"]) == normalize_version(expected)
        ]
        if len(matching_entries) > 1:
            failures.append(f"duplicate lock entries: {name}@{expected}")

        for entry in matching_entries:
            lock_options = entry.get("options", {})
            if not isinstance(lock_options, dict):
                failures.append(f"invalid lock options: {name}@{expected}")
                continue
            for option, actual in lock_options.items():
                if option not in expected_options:
                    failures.append(f"stale lock option: {name}@{expected} option={option}")
                elif option_string(actual) != option_string(expected_options[option]):
                    failures.append(
                        f"lock option mismatch: {name}@{expected} option={option} "
                        f"config={expected_options[option]} lock={actual}"
                    )

            for option in expected_options:
                if option not in lock_options:
                    failures.append(f"missing lock option: {name}@{expected} option={option}")

            for platform in platforms:
                platform_lock = lock_platform(entry, platform)
                if platform_lock is None:
                    failures.append(f"missing platform URL: {name}@{expected} platform={platform}")
                    continue
                url = platform_lock.get("url")
                if not isinstance(url, str) or not url:
                    failures.append(f"missing platform URL: {name}@{expected} platform={platform}")
                elif "{{ version }}" in config_url and expected not in url:
                    failures.append(
                        f"stale platform URL: {name}@{expected} platform={platform} url={url}"
                    )

    return failures


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

    platforms = lockfile_platforms(config)
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
        failures.extend(
            check_url_tool_lock(name, value, lock_tools[name], expected_versions, platforms)
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
