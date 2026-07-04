#!/usr/bin/env python3
"""Update mise.lock only for mise tools changed in config.toml.

This is intended for Renovate PRs: Renovate changes configured versions, GitHub
Actions regenerates only the affected lockfile sections, and autofix.ci commits
the generated lockfile diff back to the PR.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

CONFIG_PATH = "home/dot_config/mise/config.toml"
LOCK_PATH = "home/dot_config/mise/mise.lock"
DEFAULT_PLATFORMS = ["macos-arm64", "linux-x64"]


class Abort(RuntimeError):
    pass


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def run(args: list[str], *, cwd: Path, capture: bool = False) -> str:
    if capture:
        completed = subprocess.run(
            args,
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return completed.stdout
    subprocess.run(args, cwd=cwd, check=True)
    return ""


def git_show(repo: Path, ref: str, path: str) -> str:
    return run(["git", "show", f"{ref}:{path}"], cwd=repo, capture=True)


def load_toml_text(text: str, source: str) -> dict[str, Any]:
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise Abort(f"failed to parse {source}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise Abort(f"{source}: expected a TOML table")
    return parsed


def load_worktree_toml(repo: Path, path: str) -> dict[str, Any]:
    full_path = repo / path
    try:
        text = full_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise Abort(f"failed to read {path}: {exc}") from exc
    return load_toml_text(text, path)


def load_base_toml(repo: Path, ref: str, path: str) -> dict[str, Any]:
    return load_toml_text(git_show(repo, ref, path), f"{ref}:{path}")


def tools_table(config: dict[str, Any], source: str) -> dict[str, Any]:
    tools = config.get("tools", {})
    if not isinstance(tools, dict):
        raise Abort(f"{source}: [tools] must be a table")
    return tools


def config_without_tools(config: dict[str, Any]) -> dict[str, Any]:
    rest = dict(config)
    rest.pop("tools", None)
    return rest


def version_of_tool(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("version"), str):
        return value["version"]
    return None


def value_without_version(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    rest = dict(value)
    rest.pop("version", None)
    return rest


def validate_version_only_change(name: str, before: Any, after: Any) -> None:
    before_version = version_of_tool(before)
    after_version = version_of_tool(after)
    if before_version is None or after_version is None:
        raise Abort(f"unsupported non-version mise tool change: {name}")
    if isinstance(before, str) and isinstance(after, str):
        return
    if isinstance(before, dict) and isinstance(after, dict):
        if value_without_version(before) == value_without_version(after):
            return
    raise Abort(
        f"unsupported mise tool option change: {name}; only version-only changes are auto-lockable"
    )


def changed_tools(base_config: dict[str, Any], head_config: dict[str, Any]) -> list[str]:
    if config_without_tools(base_config) != config_without_tools(head_config):
        raise Abort(
            "mise config changed outside [tools]; targeted lockfile refresh is unsafe, "
            "update mise.lock manually"
        )

    base_tools = tools_table(base_config, f"base:{CONFIG_PATH}")
    head_tools = tools_table(head_config, CONFIG_PATH)

    removed = [name for name in base_tools if name not in head_tools]
    if removed:
        raise Abort(
            "mise tools were removed; targeted mise lock may leave stale entries: "
            + ", ".join(removed)
        )

    changed: list[str] = []
    added = [name for name in head_tools if name not in base_tools]
    if added:
        raise Abort(
            "mise tools were added; only version changes to existing tools are auto-lockable: "
            + ", ".join(added)
        )

    for name, after in head_tools.items():
        before = base_tools[name]
        if before == after:
            continue
        validate_version_only_change(name, before, after)
        changed.append(name)

    return changed


def lockfile_platforms(config: dict[str, Any]) -> list[str]:
    settings = config.get("settings", {})
    if not isinstance(settings, dict):
        return DEFAULT_PLATFORMS
    platforms = settings.get("lockfile_platforms", DEFAULT_PLATFORMS)
    if not isinstance(platforms, list) or not all(isinstance(item, str) for item in platforms):
        raise Abort("[settings].lockfile_platforms must be a list of strings")
    if not platforms:
        raise Abort("[settings].lockfile_platforms must not be empty")
    return platforms


def tool_from_array_header(line: str) -> str | None:
    header = line.strip()
    if not header.startswith("[[") or not header.endswith("]]"):
        return None
    try:
        parsed = tomllib.loads(f"{header}\n")
    except tomllib.TOMLDecodeError as exc:
        raise Abort(f"failed to parse lockfile header {header}: {exc}") from exc

    tools = parsed.get("tools")
    if not isinstance(tools, dict) or len(tools) != 1:
        return None
    name, entries = next(iter(tools.items()))
    if isinstance(name, str) and isinstance(entries, list):
        return name
    return None


def split_lock_sections(text: str) -> tuple[str, list[str], dict[str, str]]:
    preamble = ""
    order: list[str] = []
    sections: dict[str, str] = {}
    current_tool: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal preamble, current_lines, current_tool
        block = "".join(current_lines)
        if current_tool is None:
            preamble = block
        else:
            sections[current_tool] = sections.get(current_tool, "") + block
        current_lines = []

    for line in text.splitlines(keepends=True):
        tool = tool_from_array_header(line)
        if tool is not None:
            flush()
            current_tool = tool
            order.append(tool)
        current_lines.append(line)
    flush()
    return preamble, order, sections


def verify_lock_scope(base_lock: str, final_lock: str, allowed_tools: set[str]) -> None:
    base_preamble, base_order, base_sections = split_lock_sections(base_lock)
    final_preamble, final_order, final_sections = split_lock_sections(final_lock)
    failures: list[str] = []

    if base_preamble != final_preamble:
        failures.append("mise.lock preamble changed")
    if base_order != final_order:
        failures.append("mise.lock tool section order changed")

    for tool in sorted(final_sections.keys() - base_sections.keys()):
        if tool not in allowed_tools:
            failures.append(f"unexpected new lock section: {tool}")
    for tool in sorted(base_sections.keys() - final_sections.keys()):
        if tool not in allowed_tools:
            failures.append(f"unexpected removed lock section: {tool}")
    for tool in sorted(base_sections.keys() & final_sections.keys()):
        if tool not in allowed_tools and base_sections[tool] != final_sections[tool]:
            failures.append(f"unexpected lock section change: {tool}")

    if failures:
        raise Abort("mise.lock changed outside allowed tool sections:\n- " + "\n- ".join(failures))


def lock_entries(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def entry_platforms(entry: dict[str, Any]) -> set[str]:
    platforms: set[str] = set()
    nested = entry.get("platforms")
    if isinstance(nested, dict):
        platforms.update(key for key in nested if isinstance(key, str))
    for key in entry:
        if isinstance(key, str) and key.startswith("platforms."):
            platforms.add(key.removeprefix("platforms."))
    return platforms


def verify_changed_tool_platforms(lock_config: dict[str, Any], tools: list[str], platforms: list[str]) -> None:
    lock_tools = lock_config.get("tools", {})
    if not isinstance(lock_tools, dict):
        raise Abort(f"{LOCK_PATH}: [tools] must be a table")

    failures: list[str] = []
    for tool in tools:
        entries = lock_entries(lock_tools.get(tool))
        if not entries:
            failures.append(f"missing lock entry: {tool}")
            continue
        for entry in entries:
            present = entry_platforms(entry)
            if not present:
                continue
            missing = [platform for platform in platforms if platform not in present]
            if missing:
                failures.append(f"{tool} missing lock platforms: {', '.join(missing)}")
    if failures:
        raise Abort("mise.lock platform check failed:\n- " + "\n- ".join(failures))


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise Abort(f"failed to read {path}: {exc}") from exc


def run_consistency_check(repo: Path) -> None:
    run(["sh", str(repo / "scripts/check-mise-lock-consistency.sh")], cwd=repo)


def update_lock(repo: Path, tools: list[str], platforms: list[str]) -> None:
    mise_dir = repo / "home/dot_config/mise"
    run(["mise", "trust", "config.toml"], cwd=mise_dir)
    run(
        [
            "mise",
            "exec",
            "node",
            "--",
            "env",
            "MISE_NPM_PACKAGE_MANAGER=npm",
            "mise",
            "lock",
            "--platform",
            ",".join(platforms),
            *tools,
        ],
        cwd=mise_dir,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD", help="base git ref to compare against")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo = Path.cwd()

    try:
        base_config = load_base_toml(repo, args.base, CONFIG_PATH)
        head_config = load_worktree_toml(repo, CONFIG_PATH)
        tools = changed_tools(base_config, head_config)
        platforms = lockfile_platforms(head_config)

        if tools:
            print("mise tools changed: " + ", ".join(tools))
        else:
            print("no mise tool version changes detected")

        base_lock = git_show(repo, args.base, LOCK_PATH)
        if tools:
            update_lock(repo, tools, platforms)
        run_consistency_check(repo)

        final_lock_path = repo / LOCK_PATH
        final_lock = read_text(final_lock_path)
        verify_lock_scope(base_lock, final_lock, set(tools))
        final_lock_config = load_toml_text(final_lock, LOCK_PATH)
        verify_changed_tool_platforms(final_lock_config, tools, platforms)
        return 0
    except Abort as exc:
        eprint(str(exc))
        return 1
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            eprint(exc.stderr.rstrip())
        return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
