#!/usr/bin/env python3
"""Mark installed skills as managed by dotfiles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

LOG_PREFIX = "[skills:mark]"


def log(message: str) -> None:
    print(f"{LOG_PREFIX} {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mark skills as dotfiles-managed")
    parser.add_argument(
        "--manifest", required=True, help="Path to managed skills manifest"
    )
    parser.add_argument(
        "--agents-skills", required=True, help="Path to ~/.agents/skills"
    )
    parser.add_argument(
        "--marker", default=".dotfiles-managed", help="Managed marker filename"
    )
    return parser.parse_args()


def load_manifest(path: Path) -> list[str]:
    if not path.is_file():
        raise SystemExit(f"Manifest file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    skills = payload.get("skills")

    if not isinstance(skills, list):
        raise SystemExit("Manifest format error: skills must be an array")

    result: list[str] = []
    for item in skills:
        if isinstance(item, str):
            result.append(item)

    return result


def main() -> int:
    args = parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    agents_skills = Path(args.agents_skills).expanduser().resolve()

    skills = load_manifest(manifest_path)
    if not skills:
        log("managed_skills=0 (nothing to mark)")
        return 0

    missing: list[str] = []
    marked = 0

    for skill in skills:
        skill_dir = agents_skills / skill
        if not skill_dir.is_dir():
            missing.append(skill)
            continue

        marker_path = skill_dir / args.marker
        marker_path.write_text("managed-by-dotfiles\n", encoding="utf-8")
        marked += 1

    log(f"marked={marked}")
    if missing:
        log(f"missing={len(missing)} names={','.join(sorted(missing))}")
    else:
        log("missing=0")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
