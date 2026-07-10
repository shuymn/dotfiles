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
from pathlib import Path

from mise_lock_policy import LockPolicyError, plan_update, verify_candidate

CONFIG_PATH = "home/dot_config/mise/config.toml"
LOCK_PATH = "home/dot_config/mise/mise.lock"


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


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise Abort(f"failed to read {path}: {exc}") from exc


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
        plan = plan_update(base_config_text, head_config_text)
        tools = list(plan.changed_tools)
        platforms = list(plan.platforms)

        print("mise tools changed: " + ", ".join(tools))

        base_lock = git_show(repo, args.base, LOCK_PATH)
        update_lock(repo, tools, platforms)

        final_lock_path = repo / LOCK_PATH
        final_lock = read_text(final_lock_path)
        verify_candidate(base_config_text, head_config_text, base_lock, final_lock)
        return 0
    except (Abort, LockPolicyError) as exc:
        eprint(str(exc))
        return 1
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            eprint(exc.stderr.rstrip())
        return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
