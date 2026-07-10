#!/usr/bin/env python3
"""Update mise.lock only for mise tools changed in config.toml.

This is intended for Renovate PRs: Renovate changes configured versions and
GitHub Actions regenerates only the affected lockfile sections for the trusted
reconciler to commit back to the PR.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from mise_lock_candidate import CandidateError, changed_tools, verify_candidate

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
        base_config_text = git_show(repo, args.base, CONFIG_PATH)
        head_config_text = read_text(repo / CONFIG_PATH)
        head_config = load_toml_text(head_config_text, CONFIG_PATH)
        tools = list(changed_tools(base_config_text, head_config_text))
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
        verify_candidate(base_config_text, head_config_text, base_lock, final_lock)
        return 0
    except (Abort, CandidateError) as exc:
        eprint(str(exc))
        return 1
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            eprint(exc.stderr.rstrip())
        return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
