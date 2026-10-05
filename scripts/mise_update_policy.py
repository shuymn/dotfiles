"""Select mise tool updates and render their reports.

Everything here is pure: callers fetch release metadata and write files.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

VERSION_PATTERN = re.compile(r"v?(\d+(?:\.\d+)*)")
DATE_ONLY_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


class UpdatePolicyError(ValueError):
    """Raised when a config cannot be updated safely."""


@dataclass(frozen=True)
class Release:
    version: str
    created_at: datetime | None


@dataclass(frozen=True)
class Hold:
    version: str
    reason: str


@dataclass(frozen=True)
class Decision:
    tool: str
    current: str
    target: Release | None
    holds: tuple[Hold, ...]


def parse_version(text: str) -> tuple[int, ...] | None:
    """Parse plain numeric versions; prereleases and suffixed builds return None."""
    match = VERSION_PATTERN.fullmatch(text)
    if match is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def parse_timestamp(value: Any) -> datetime | None:
    """Parse release metadata timestamps as aware UTC datetimes.

    Date-only values are treated as the end of that day so the age check never
    overstates how old a release is.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        if DATE_ONLY_PATTERN.fullmatch(value):
            day = date.fromisoformat(value)
            return datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=1)
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def releases_from_metadata(entries: Any) -> list[Release]:
    """Convert `mise ls-remote --json` output into releases."""
    if not isinstance(entries, list):
        raise UpdatePolicyError("release metadata must be a JSON array")
    releases = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("version"), str):
            continue
        if entry.get("prerelease") is True:
            continue
        releases.append(Release(entry["version"], parse_timestamp(entry.get("created_at"))))
    return releases


def _with_prefix_of(current: str, version: str) -> str:
    bare = version.removeprefix("v")
    return f"v{bare}" if current.startswith("v") else bare


def select_update(
    tool: str,
    current: str,
    releases: list[Release],
    *,
    now: datetime,
    minimum_age: timedelta,
) -> Decision:
    """Pick the newest release in the current major line that is old enough.

    Newer releases that were skipped are returned as holds, keeping only the
    newest version per reason.
    """
    current_key = parse_version(current)
    if current_key is None:
        return Decision(tool, current, None, (Hold(current, "unsupported version format"),))

    eligible: list[tuple[tuple[int, ...], Release]] = []
    held: dict[str, tuple[tuple[int, ...], str]] = {}
    for release in releases:
        key = parse_version(release.version)
        if key is None or key <= current_key:
            continue
        if key[0] != current_key[0]:
            reason = "major update"
        elif release.created_at is None:
            reason = "no release timestamp"
        elif now - release.created_at < minimum_age:
            reason = "released less than the minimum age ago"
        else:
            eligible.append((key, release))
            continue
        if reason not in held or key > held[reason][0]:
            held[reason] = (key, release.version)

    target = max(eligible, key=lambda item: item[0]) if eligible else None
    floor = target[0] if target else current_key
    holds = tuple(
        Hold(_with_prefix_of(current, version), reason)
        for reason, (key, version) in sorted(held.items())
        if key > floor
    )
    if target is None:
        return Decision(tool, current, None, holds)
    selected = Release(_with_prefix_of(current, target[1].version), target[1].created_at)
    return Decision(tool, current, selected, holds)


def configured_versions(config_text: str) -> tuple[dict[str, str], list[str]]:
    """Return plain-string [tools] versions and the names of other entries."""
    try:
        config = tomllib.loads(config_text)
    except tomllib.TOMLDecodeError as exc:
        raise UpdatePolicyError(f"failed to parse mise config: {exc}") from exc
    tools = config.get("tools", {})
    if not isinstance(tools, dict):
        raise UpdatePolicyError("[tools] must be a table")

    versions = {name: value for name, value in tools.items() if isinstance(value, str)}
    unsupported = [name for name in tools if name not in versions]
    return versions, unsupported


def replace_version(config_text: str, tool: str, old: str, new: str) -> str:
    """Replace one [tools] version string while keeping the rest of the file intact."""
    lines = config_text.splitlines(keepends=True)
    section: str | None = None
    matches: list[int] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped
            continue
        if section != "[tools]" or not stripped or stripped.startswith("#"):
            continue
        try:
            parsed = tomllib.loads(line)
        except tomllib.TOMLDecodeError:
            continue
        if parsed == {tool: old}:
            matches.append(index)

    if len(matches) != 1:
        raise UpdatePolicyError(f"expected one [tools] line for {tool} = {old!r}, found {len(matches)}")
    index = matches[0]
    quoted = f'"{old}"'
    before, separator, after = lines[index].rpartition(quoted)
    if not separator:
        raise UpdatePolicyError(f"{tool} must use a double-quoted version string")
    lines[index] = f'{before}"{new}"{after}'

    updated = "".join(lines)
    if tomllib.loads(updated).get("tools", {}).get(tool) != new:
        raise UpdatePolicyError(f"failed to update {tool}")
    return updated


def validated_changes(base_config_text: str, head_config_text: str) -> list[tuple[str, str, str]]:
    """Return (tool, old, new) for [tools] changes that move forward within a major line."""
    base_versions, _ = configured_versions(base_config_text)
    head_versions, _ = configured_versions(head_config_text)
    changes = []
    for tool, new in head_versions.items():
        old = base_versions.get(tool)
        if old is None or old == new:
            continue
        old_key, new_key = parse_version(old), parse_version(new)
        if old_key is None or new_key is None:
            raise UpdatePolicyError(f"{tool}: versions must be numeric ({old} -> {new})")
        if new_key[0] != old_key[0] or new_key <= old_key:
            raise UpdatePolicyError(
                f"{tool}: only newer versions in the same major line are allowed ({old} -> {new})"
            )
        changes.append((tool, old, new))
    if not changes:
        raise UpdatePolicyError("no mise tool version changes detected")
    return changes


def render_pull_request(changes: list[tuple[str, str, str]], *, run_url: str) -> tuple[str, str]:
    """Render the pull request title and body from validated changes."""
    if len(changes) == 1:
        tool, _, new = changes[0]
        title = f"Update mise tool {tool} to {new}"
    else:
        names = [tool for tool, _, _ in changes]
        shown = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
        title = f"Update mise tools: {shown}"
    lines = ["| Tool | From | To |", "| --- | --- | --- |"]
    lines += [f"| `{tool}` | {old} | {new} |" for tool, old, new in changes]
    lines += ["", f"Held-back updates are listed in the [workflow run]({run_url}) summary."]
    return title, "\n".join(lines) + "\n"


def _released(release: Release) -> str:
    return release.created_at.strftime("%Y-%m-%d") if release.created_at else "-"


def render_report(decisions: list[Decision], *, source: str) -> str:
    """Render a Markdown report for the workflow job summary."""
    updates = [decision for decision in decisions if decision.target is not None]
    holds = [(decision.tool, hold) for decision in decisions for hold in decision.holds]
    lines = ["## mise tool updates", ""]
    if updates:
        lines += ["| Tool | From | To | Released |", "| --- | --- | --- | --- |"]
        for decision in updates:
            assert decision.target is not None
            lines.append(
                f"| `{decision.tool}` | {decision.current} | {decision.target.version} "
                f"| {_released(decision.target)} |"
            )
    else:
        lines.append("No updates are eligible.")
    if holds:
        lines += ["", "### Held back", "", "| Tool | Version | Reason |", "| --- | --- | --- |"]
        lines += [f"| `{tool}` | {hold.version} | {hold.reason} |" for tool, hold in holds]
    lines += ["", f"Generated from {source}."]
    return "\n".join(lines) + "\n"
