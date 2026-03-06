#!/usr/bin/env python3
"""Reconcile managed skills without touching external skills."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path

LOG_PREFIX = "[skills:reconcile]"


def log(message: str) -> None:
    print(f"{LOG_PREFIX} {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile managed skills")
    parser.add_argument(
        "--manifest", required=True, help="Path to managed skills manifest"
    )
    parser.add_argument(
        "--agents-skills", required=True, help="Path to ~/.agents/skills"
    )
    parser.add_argument(
        "--marker", default=".dotfiles-managed", help="Managed marker filename"
    )
    parser.add_argument(
        "--skills-cmd",
        required=True,
        help="Skills CLI command prefix (example: 'bunx --bun skills@1.4.4')",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> set[str]:
    if not path.is_file():
        raise SystemExit(f"Manifest file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    skills = payload.get("skills")

    if not isinstance(skills, list):
        raise SystemExit("Manifest format error: skills must be an array")

    desired = {item for item in skills if isinstance(item, str)}
    if not desired:
        raise SystemExit("Safety stop: manifest has zero managed skills")

    return desired


def discover_managed_installed(agents_skills: Path, marker: str) -> set[str]:
    if not agents_skills.is_dir():
        return set()

    managed: set[str] = set()

    for child in agents_skills.iterdir():
        if not child.is_dir():
            continue
        if (child / marker).is_file():
            managed.add(child.name)

    return managed


def run_remove_command(skills_cmd: str, to_remove: list[str]) -> None:
    cmd = shlex.split(skills_cmd)
    if not cmd:
        raise SystemExit("Invalid skills command")

    cmd.extend(["remove", "-g", "-y"])
    cmd.extend(to_remove)

    log(f"run={' '.join(shlex.quote(part) for part in cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            f"Skills removal failed (exit {e.returncode}): {' '.join(shlex.quote(p) for p in cmd)}"
        )


def main() -> int:
    args = parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    agents_skills = Path(args.agents_skills).expanduser().resolve()

    desired = load_manifest(manifest_path)
    managed_installed = discover_managed_installed(agents_skills, args.marker)
    to_remove = sorted(managed_installed - desired)

    log(
        f"desired={len(desired)} installed={len(managed_installed)} remove={len(to_remove)}"
    )

    if not to_remove:
        log("result=no_stale_managed_skills")
        return 0

    log(f"remove_names={','.join(to_remove)}")

    run_remove_command(args.skills_cmd, to_remove)
    log(f"removed={len(to_remove)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
