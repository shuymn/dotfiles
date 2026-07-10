"""Validate a generated mise.lock candidate as untrusted data."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from typing import Any


class CandidateError(ValueError):
    """Raised when a candidate is not a safe projection of a config update."""


@dataclass(frozen=True)
class CandidateValidation:
    changed_tools: tuple[str, ...]
    sha256: str


def _parse_toml(text: str, source: str) -> dict[str, Any]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise CandidateError(f"failed to parse {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise CandidateError(f"{source}: expected a TOML table")
    return data


def _tools(config: dict[str, Any], source: str) -> dict[str, Any]:
    tools = config.get("tools", {})
    if not isinstance(tools, dict):
        raise CandidateError(f"{source}: [tools] must be a table")
    return tools


def _version(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("version"), str):
        return value["version"]
    return None


def _normalize_version(version: str) -> str:
    return version.removeprefix("v")


def _without_version(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    result.pop("version", None)
    return result


def changed_tools(base_config_text: str, head_config_text: str) -> tuple[str, ...]:
    """Return tools with version-only changes, rejecting every other config change."""
    base = _parse_toml(base_config_text, "base config")
    head = _parse_toml(head_config_text, "head config")
    base_without_tools = dict(base)
    base_without_tools.pop("tools", None)
    head_without_tools = dict(head)
    head_without_tools.pop("tools", None)
    if base_without_tools != head_without_tools:
        raise CandidateError("mise config changed outside [tools]")

    base_tools = _tools(base, "base config")
    head_tools = _tools(head, "head config")
    if base_tools.keys() != head_tools.keys():
        raise CandidateError("mise tools were added or removed")

    changed = []
    for name, after in head_tools.items():
        before = base_tools[name]
        if before == after:
            continue
        if _version(before) is None or _version(after) is None:
            raise CandidateError(f"unsupported non-version mise tool change: {name}")
        if isinstance(before, str) and isinstance(after, str):
            changed.append(name)
            continue
        if not (
            isinstance(before, dict)
            and isinstance(after, dict)
            and _without_version(before) == _without_version(after)
        ):
            raise CandidateError(f"unsupported mise tool option change: {name}")
        changed.append(name)
    if not changed:
        raise CandidateError("no mise tool version changes detected")
    return tuple(changed)


def _lock_sections(lock: dict[str, Any], source: str) -> dict[str, Any]:
    tools = lock.get("tools", {})
    if not isinstance(tools, dict):
        raise CandidateError(f"{source}: [tools] must be a table")
    return tools


def _lock_entries(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _entry_platforms(entry: dict[str, Any]) -> set[str]:
    platforms: set[str] = set()
    nested = entry.get("platforms")
    if isinstance(nested, dict):
        platforms.update(name for name in nested if isinstance(name, str))
    platforms.update(
        key.removeprefix("platforms.")
        for key in entry
        if isinstance(key, str) and key.startswith("platforms.")
    )
    return platforms


def _configured_platforms(config: dict[str, Any]) -> set[str]:
    settings = config.get("settings", {})
    if not isinstance(settings, dict):
        return set()
    platforms = settings.get("lockfile_platforms", [])
    if not isinstance(platforms, list) or not all(
        isinstance(platform, str) and platform for platform in platforms
    ):
        raise CandidateError("head config: lockfile_platforms must be a list of strings")
    return set(platforms)


def _tool_from_header(line: str) -> str | None:
    header = line.strip()
    if not header.startswith("[[") or not header.endswith("]]"):
        return None
    try:
        parsed = tomllib.loads(header + "\n")
    except tomllib.TOMLDecodeError as exc:
        raise CandidateError(f"failed to parse lock header {header}: {exc}") from exc
    tools = parsed.get("tools")
    if not isinstance(tools, dict) or len(tools) != 1:
        return None
    name, entries = next(iter(tools.items()))
    return name if isinstance(name, str) and isinstance(entries, list) else None


def _split_lock_text(text: str) -> tuple[str, list[str], dict[str, str]]:
    preamble = ""
    order: list[str] = []
    sections: dict[str, str] = {}
    current_tool: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal preamble, current_lines
        block = "".join(current_lines)
        if current_tool is None:
            preamble = block
        else:
            sections[current_tool] = sections.get(current_tool, "") + block
        current_lines = []

    for line in text.splitlines(keepends=True):
        tool = _tool_from_header(line)
        if tool is not None:
            flush()
            current_tool = tool
            order.append(tool)
        current_lines.append(line)
    flush()
    return preamble, order, sections


def verify_candidate(
    base_config_text: str,
    head_config_text: str,
    base_lock_text: str,
    candidate_lock_text: str,
) -> CandidateValidation:
    """Verify that candidate_lock is the exact lock projection of a version-only update."""
    base_config = _parse_toml(base_config_text, "base config")
    head_config = _parse_toml(head_config_text, "head config")
    base_lock = _parse_toml(base_lock_text, "base lock")
    candidate_lock = _parse_toml(candidate_lock_text, "candidate lock")
    changed_tool_names = changed_tools(base_config_text, head_config_text)

    base_lock_metadata = dict(base_lock)
    base_lock_metadata.pop("tools", None)
    candidate_lock_metadata = dict(candidate_lock)
    candidate_lock_metadata.pop("tools", None)
    if base_lock_metadata != candidate_lock_metadata:
        raise CandidateError("candidate changed lock data outside tool sections")

    base_preamble, base_order, base_text_sections = _split_lock_text(base_lock_text)
    candidate_preamble, candidate_order, candidate_text_sections = _split_lock_text(
        candidate_lock_text
    )
    if base_preamble != candidate_preamble:
        raise CandidateError("candidate changed lock preamble")
    if base_order != candidate_order:
        raise CandidateError("candidate changed lock section order")
    for name in base_text_sections.keys() | candidate_text_sections.keys():
        if (
            name not in changed_tool_names
            and base_text_sections.get(name) != candidate_text_sections.get(name)
        ):
            raise CandidateError(f"candidate changed unrelated lock section: {name}")

    base_sections = _lock_sections(base_lock, "base lock")
    candidate_sections = _lock_sections(candidate_lock, "candidate lock")
    for name in base_sections.keys() | candidate_sections.keys():
        if name not in changed_tool_names and base_sections.get(name) != candidate_sections.get(
            name
        ):
            raise CandidateError(f"candidate changed unrelated lock section: {name}")

    head_tools = _tools(head_config, "head config")
    configured_platforms = _configured_platforms(head_config)
    for name in changed_tool_names:
        expected = _version(head_tools[name])
        base_entries = _lock_entries(base_sections.get(name))
        entries = _lock_entries(candidate_sections.get(name))
        if len(base_entries) != 1 or len(entries) != 1:
            raise CandidateError(f"candidate lock must contain one entry: {name}")
        base_entry = base_entries[0]
        entry = entries[0]
        if entry.get("backend") != base_entry.get("backend"):
            raise CandidateError(f"candidate changed lock backend: {name}")
        if entry.get("options") != base_entry.get("options"):
            raise CandidateError(f"candidate changed lock options: {name}")

        base_platforms = _entry_platforms(base_entry)
        candidate_platforms = _entry_platforms(entry)
        if base_platforms and not configured_platforms <= candidate_platforms:
            missing = ", ".join(sorted(configured_platforms - candidate_platforms))
            raise CandidateError(f"candidate lock is missing configured platforms for {name}: {missing}")

        actual_versions = {
            _normalize_version(version)
            for entry in entries
            if isinstance((version := entry.get("version")), str)
        }
        if expected is None or actual_versions != {_normalize_version(expected)}:
            raise CandidateError(f"candidate lock version mismatch: {name}")

    return CandidateValidation(
        changed_tools=changed_tool_names,
        sha256=hashlib.sha256(candidate_lock_text.encode()).hexdigest(),
    )
