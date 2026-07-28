#!/usr/bin/env python3
"""Helper subcommands for check-mise-renovate-age.sh."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise TypeError(f"{path}: expected a JSON object")
    return data


def check_renovate_config(config_path: Path) -> int:
    config = load_json(config_path)

    failures = []
    if config.get("platformAutomerge") is not True:
        failures.append(
            "platformAutomerge must stay explicitly enabled; automerge-gate/all-passed is the GitHub automerge gate"
        )

    if "mise" in (config.get("allowedUnsafeExecutions") or []):
        failures.append(
            "allowedUnsafeExecutions must not include mise; mise.lock is owned by the GitHub reconciler"
        )

    skip_artifacts_update = False
    lock_file_maintenance_disabled = False
    for rule in config.get("packageRules", []) or []:
        managers = rule.get("matchManagers") or []
        commands = "\n".join((rule.get("postUpgradeTasks") or {}).get("commands") or [])
        file_names = rule.get("matchFileNames") or []
        if "mise" in managers:
            if rule.get("skipArtifactsUpdate") is True:
                skip_artifacts_update = True
            if (rule.get("lockFileMaintenance") or {}).get("enabled") is False:
                lock_file_maintenance_disabled = True
        if rule.get("postUpgradeTasks") and (
            "mise lock" in commands or "home/dot_config/mise/config.toml" in file_names
        ):
            failures.append("mise lock postUpgradeTasks must stay out of Renovate config")

    if not skip_artifacts_update:
        failures.append("Renovate mise manager must keep skipArtifactsUpdate=true")
    if not lock_file_maintenance_disabled:
        failures.append(
            "Renovate mise manager must keep lockFileMaintenance.enabled=false"
        )

    if failures:
        sys.stderr.write("Renovate/mise lock ownership check failed:\n")
        for failure in failures:
            sys.stderr.write(f"- {failure}\n")
        return 1
    return 0


def load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:
        sys.stderr.write("Python 3.11+ with tomllib is required to parse mise TOML\n")
        sys.exit(2)

    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except Exception as exc:
        sys.stderr.write(f"failed to parse {path}: {exc}\n")
        sys.exit(2)
    return data


def parse_version(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    if isinstance(value, dict) and isinstance(value.get("version"), str):
        return value["version"]
    return ""


def emit_tools(tools: Any) -> None:
    if not isinstance(tools, dict):
        return
    for name, value in tools.items():
        version = parse_version(value)
        if version:
            print(f"{name}\t{version}")


def emit_mise_tools(config_path: Path) -> int:
    data = load_toml(config_path)
    emit_tools(data.get("tools", {}))
    for task in (data.get("tasks", {}) or {}).values():
        if isinstance(task, dict):
            emit_tools(task.get("tools", {}))
    return 0


def emit_registry_tools(registry_path: Path) -> int:
    registry = load_json(registry_path)

    for tool, backends in (registry.get("tools", {}) or {}).items():
        if not isinstance(backends, dict):
            continue
        if "github" in backends:
            backend = "github"
        else:
            backend = next(iter(backends), "")
        if not backend:
            continue
        name = backends.get(backend) or tool
        print(f"{tool}\t{backend}\t{name}")
    return 0


def emit_renovate_overrides(
    config_path: Path,
    regex_tracked_path: Path,
    disabled_mise_path: Path,
) -> int:
    config = load_json(config_path)

    with regex_tracked_path.open("w", encoding="utf-8") as regex_tracked:
        for manager in config.get("customManagers", []):
            if manager.get("customType") != "regex":
                continue
            for pattern in manager.get("matchStrings", []) or []:
                pattern = re.sub(r"^\(\?m\)", "", pattern)
                pattern = re.sub(r"^\\n", "", pattern)
                pattern = re.sub(r"^\^", "", pattern)
                match = re.match(
                    r"(?:\\?[\"'])?([A-Za-z0-9@/:_.-]+)(?:\\?[\"'])?(?:\s|\\s[+*?]?)*=",
                    pattern,
                )
                if match:
                    regex_tracked.write(f"{match.group(1)}\n")

    with disabled_mise_path.open("w", encoding="utf-8") as disabled_mise:
        for rule in config.get("packageRules", []) or []:
            if rule.get("enabled") is not False:
                continue
            if "mise" not in (rule.get("matchManagers") or []):
                continue
            for dep_name in rule.get("matchDepNames", []) or []:
                disabled_mise.write(f"{dep_name}\n")
    return 0


def usage(program: str) -> str:
    return (
        f"usage: {program} COMMAND [ARGS...]\n"
        "commands:\n"
        "  check-renovate-config RENOVATE_CONFIG\n"
        "  emit-mise-tools MISE_CONFIG\n"
        "  emit-registry-tools MISE_REGISTRY_JSON\n"
        "  emit-renovate-overrides RENOVATE_CONFIG REGEX_TRACKED_OUT DISABLED_MISE_OUT\n"
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write(usage(argv[0]))
        return 2

    command = argv[1]
    args = argv[2:]
    if command == "check-renovate-config" and len(args) == 1:
        return check_renovate_config(Path(args[0]))
    if command == "emit-mise-tools" and len(args) == 1:
        return emit_mise_tools(Path(args[0]))
    if command == "emit-registry-tools" and len(args) == 1:
        return emit_registry_tools(Path(args[0]))
    if command == "emit-renovate-overrides" and len(args) == 3:
        return emit_renovate_overrides(Path(args[0]), Path(args[1]), Path(args[2]))

    sys.stderr.write(usage(argv[0]))
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
