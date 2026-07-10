"""Define and validate repository mise lock projections."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from typing import Any

DEFAULT_PLATFORMS = ("macos-arm64", "linux-x64")


class LockPolicyError(ValueError):
    """Raised when a config or lock violates repository policy."""


@dataclass(frozen=True)
class CandidateValidation:
    changed_tools: tuple[str, ...]
    sha256: str


@dataclass(frozen=True)
class LockValidation:
    checked_tools: int


@dataclass(frozen=True)
class UpdatePlan:
    changed_tools: tuple[str, ...]
    platforms: tuple[str, ...]


def _parse_toml(text: str, source: str) -> dict[str, Any]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise LockPolicyError(f"failed to parse {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise LockPolicyError(f"{source}: expected a TOML table")
    return data


def _tool_sections(document: dict[str, Any], source: str) -> dict[str, Any]:
    tools = document.get("tools", {})
    if not isinstance(tools, dict):
        raise LockPolicyError(f"{source}: [tools] must be a table")
    return tools


def _version(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("version"), str):
        return value["version"]
    return None


def _versions(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    version = _version(value)
    return [version] if version is not None else []


def _normalize_version(version: str) -> str:
    return version.removeprefix("v")


def _without_version(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    result.pop("version", None)
    return result


def _changed_tools(base: dict[str, Any], head: dict[str, Any]) -> tuple[str, ...]:
    """Return tools with version-only changes, rejecting every other config change."""
    base_without_tools = dict(base)
    base_without_tools.pop("tools", None)
    head_without_tools = dict(head)
    head_without_tools.pop("tools", None)
    if base_without_tools != head_without_tools:
        raise LockPolicyError("mise config changed outside [tools]")

    base_tools = _tool_sections(base, "base config")
    head_tools = _tool_sections(head, "head config")
    if base_tools.keys() != head_tools.keys():
        raise LockPolicyError("mise tools were added or removed")

    changed = []
    for name, after in head_tools.items():
        before = base_tools[name]
        if before == after:
            continue
        if _version(before) is None or _version(after) is None:
            raise LockPolicyError(f"unsupported non-version mise tool change: {name}")
        if isinstance(before, str) and isinstance(after, str):
            changed.append(name)
            continue
        if not (
            isinstance(before, dict)
            and isinstance(after, dict)
            and _without_version(before) == _without_version(after)
        ):
            raise LockPolicyError(f"unsupported mise tool option change: {name}")
        changed.append(name)
    if not changed:
        raise LockPolicyError("no mise tool version changes detected")
    return tuple(changed)


def _lock_entries(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _platform_values(entry: dict[str, Any]) -> dict[str, Any]:
    platforms = {
        key.removeprefix("platforms."): value
        for key, value in entry.items()
        if isinstance(key, str) and key.startswith("platforms.")
    }
    nested = entry.get("platforms")
    if isinstance(nested, dict):
        platforms.update({name: value for name, value in nested.items() if isinstance(name, str)})
    return platforms


def _configured_platforms(config: dict[str, Any], source: str) -> tuple[str, ...]:
    settings = config.get("settings", {})
    if not isinstance(settings, dict):
        return DEFAULT_PLATFORMS
    platforms = settings.get("lockfile_platforms")
    if platforms is None:
        return DEFAULT_PLATFORMS
    if not isinstance(platforms, list) or not all(
        isinstance(platform, str) and platform for platform in platforms
    ):
        raise LockPolicyError(f"{source}: lockfile_platforms must be a list of strings")
    if not platforms:
        raise LockPolicyError(f"{source}: lockfile_platforms must not be empty")
    return tuple(platforms)


def plan_update(base_config_text: str, head_config_text: str) -> UpdatePlan:
    """Plan a version-only lock update from trusted config text."""
    base_config = _parse_toml(base_config_text, "base config")
    head_config = _parse_toml(head_config_text, "head config")
    return UpdatePlan(
        changed_tools=_changed_tools(base_config, head_config),
        platforms=_configured_platforms(head_config, "head config"),
    )


def _config_lock_options(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    config_only_keys = {"version", "url", "bin"}
    return {key: option for key, option in value.items() if key not in config_only_keys}


def _option_string(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _lock_platform(entry: dict[str, Any], platform: str) -> dict[str, Any] | None:
    value = _platform_values(entry).get(platform)
    return value if isinstance(value, dict) else None


def _http_lock_failures(
    name: str,
    config_value: Any,
    entries: list[dict[str, Any]],
    expected_versions: list[str],
    platforms: tuple[str, ...],
) -> list[str]:
    if not (
        name.startswith("http:")
        and isinstance(config_value, dict)
        and isinstance(config_value.get("url"), str)
    ):
        return []

    failures: list[str] = []
    expected_options = _config_lock_options(config_value)
    config_url = config_value["url"]
    for expected in expected_versions:
        matching_entries = [
            entry
            for entry in entries
            if isinstance(entry.get("version"), str)
            and _normalize_version(entry["version"]) == _normalize_version(expected)
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
                elif _option_string(actual) != _option_string(expected_options[option]):
                    failures.append(
                        f"lock option mismatch: {name}@{expected} option={option} "
                        f"config={expected_options[option]} lock={actual}"
                    )
            for option in expected_options:
                if option not in lock_options:
                    failures.append(f"missing lock option: {name}@{expected} option={option}")

            for platform in sorted(platforms):
                platform_lock = _lock_platform(entry, platform)
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


def _verify_lock(config: dict[str, Any], lock: dict[str, Any]) -> LockValidation:
    config_tools = _tool_sections(config, "mise config")
    lock_tools = _tool_sections(lock, "mise lock")
    platforms = _configured_platforms(config, "mise config")
    failures: list[str] = []
    checked = 0

    for name, config_value in config_tools.items():
        expected_versions = _versions(config_value)
        if not expected_versions:
            continue
        checked += 1
        if name not in lock_tools:
            failures.append(f"missing lock entry: {name} (expected {', '.join(expected_versions)})")
            continue

        entries = _lock_entries(lock_tools[name])
        actual_versions = [
            entry["version"]
            for entry in entries
            if isinstance(entry.get("version"), str)
        ]
        if not actual_versions:
            failures.append(f"invalid lock entry: {name} (expected {', '.join(expected_versions)})")
            continue

        normalized_actual = {_normalize_version(version) for version in actual_versions}
        for expected in expected_versions:
            if _normalize_version(expected) not in normalized_actual:
                failures.append(
                    f"version mismatch: {name} config={expected} lock={', '.join(actual_versions)}"
                )
        failures.extend(
            _http_lock_failures(name, config_value, entries, expected_versions, platforms)
        )

    if checked == 0:
        raise LockPolicyError("no top-level [tools] entries found in mise config")
    if failures:
        raise LockPolicyError("mise lock consistency check failed:\n- " + "\n- ".join(failures))
    return LockValidation(checked_tools=checked)


def verify_lock(config_text: str, lock_text: str) -> LockValidation:
    """Verify that every configured tool has a matching lock projection."""
    return _verify_lock(
        _parse_toml(config_text, "mise config"),
        _parse_toml(lock_text, "mise lock"),
    )


def _tool_from_header(line: str) -> str | None:
    header = line.strip()
    if not header.startswith("[[") or not header.endswith("]]"):
        return None
    try:
        parsed = tomllib.loads(header + "\n")
    except tomllib.TOMLDecodeError as exc:
        raise LockPolicyError(f"failed to parse lock header {header}: {exc}") from exc
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
    changed_tool_names = _changed_tools(base_config, head_config)

    base_lock_metadata = dict(base_lock)
    base_lock_metadata.pop("tools", None)
    candidate_lock_metadata = dict(candidate_lock)
    candidate_lock_metadata.pop("tools", None)
    if base_lock_metadata != candidate_lock_metadata:
        raise LockPolicyError("candidate changed lock data outside tool sections")

    base_preamble, base_order, base_text_sections = _split_lock_text(base_lock_text)
    candidate_preamble, candidate_order, candidate_text_sections = _split_lock_text(
        candidate_lock_text
    )
    if base_preamble != candidate_preamble:
        raise LockPolicyError("candidate changed lock preamble")
    if base_order != candidate_order:
        raise LockPolicyError("candidate changed lock section order")
    for name in base_text_sections.keys() | candidate_text_sections.keys():
        if (
            name not in changed_tool_names
            and base_text_sections.get(name) != candidate_text_sections.get(name)
        ):
            raise LockPolicyError(f"candidate changed unrelated lock section: {name}")

    base_sections = _tool_sections(base_lock, "base lock")
    candidate_sections = _tool_sections(candidate_lock, "candidate lock")
    for name in base_sections.keys() | candidate_sections.keys():
        if name not in changed_tool_names and base_sections.get(name) != candidate_sections.get(
            name
        ):
            raise LockPolicyError(f"candidate changed unrelated lock section: {name}")

    head_tools = _tool_sections(head_config, "head config")
    configured_platforms = set(_configured_platforms(head_config, "head config"))
    for name in changed_tool_names:
        expected = _version(head_tools[name])
        base_entries = _lock_entries(base_sections.get(name))
        entries = _lock_entries(candidate_sections.get(name))
        if len(base_entries) != 1 or len(entries) != 1:
            raise LockPolicyError(f"candidate lock must contain one entry: {name}")
        base_entry = base_entries[0]
        entry = entries[0]
        if entry.get("backend") != base_entry.get("backend"):
            raise LockPolicyError(f"candidate changed lock backend: {name}")
        if entry.get("options") != base_entry.get("options"):
            raise LockPolicyError(f"candidate changed lock options: {name}")

        base_platforms = set(_platform_values(base_entry))
        candidate_platforms = set(_platform_values(entry))
        if base_platforms and not configured_platforms <= candidate_platforms:
            missing = ", ".join(sorted(configured_platforms - candidate_platforms))
            raise LockPolicyError(f"candidate lock is missing configured platforms for {name}: {missing}")

        actual_versions = {
            _normalize_version(version)
            for entry in entries
            if isinstance((version := entry.get("version")), str)
        }
        if expected is None or actual_versions != {_normalize_version(expected)}:
            raise LockPolicyError(f"candidate lock version mismatch: {name}")

    _verify_lock(head_config, candidate_lock)
    return CandidateValidation(
        changed_tools=changed_tool_names,
        sha256=hashlib.sha256(candidate_lock_text.encode()).hexdigest(),
    )
