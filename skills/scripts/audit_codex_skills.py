#!/usr/bin/env python3
"""Audit ~/.codex/skills entries and optionally prune duplicates."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

LOG_PREFIX = "[skills:codex-audit]"


def log(message: str) -> None:
    print(f"{LOG_PREFIX} {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Codex legacy skills directory")
    parser.add_argument("--manifest", required=True, help="Path to managed skills manifest")
    parser.add_argument("--agents-skills", required=True, help="Path to ~/.agents/skills")
    parser.add_argument("--codex-skills", required=True, help="Path to ~/.codex/skills")
    parser.add_argument("--marker", default=".dotfiles-managed", help="Managed marker filename")
    parser.add_argument(
        "--prune-duplicates",
        action="store_true",
        help="Remove entries from ~/.codex/skills when the same entry exists in ~/.agents/skills",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> set[str]:
    if not path.is_file():
        raise SystemExit(f"Manifest file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    skills = payload.get("skills")
    if not isinstance(skills, list):
        raise SystemExit("Manifest format error: skills must be an array")

    return {item for item in skills if isinstance(item, str)}


def list_skill_entries(path: Path) -> list[str]:
    if not path.is_dir():
        return []

    entries: list[str] = []
    for child in sorted(path.iterdir()):
        if child.is_dir():
            entries.append(child.name)
    return entries


def main() -> int:
    args = parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    agents_skills = Path(args.agents_skills).expanduser().resolve()
    codex_skills = Path(args.codex_skills).expanduser().resolve()

    managed = load_manifest(manifest_path)

    if not codex_skills.exists():
        log(f"codex_dir_missing={codex_skills}")
        return 0

    codex_entries = list_skill_entries(codex_skills)

    if not codex_entries:
        log(f"codex_dir_empty={codex_skills}")
        return 0

    duplicate_entries: list[str] = []
    managed_duplicates: list[str] = []
    external_duplicates: list[str] = []
    codex_only_entries: list[str] = []

    for name in codex_entries:
        agents_skill_dir = agents_skills / name
        has_marker = (agents_skill_dir / args.marker).is_file()
        exists_in_agents = agents_skill_dir.is_dir()

        if exists_in_agents:
            duplicate_entries.append(name)
            if name in managed or has_marker:
                managed_duplicates.append(name)
            else:
                external_duplicates.append(name)
        else:
            codex_only_entries.append(name)

    log(
        "totals "
        + f"codex={len(codex_entries)} "
        + f"duplicates={len(duplicate_entries)} "
        + f"managed_duplicates={len(managed_duplicates)} "
        + f"external_duplicates={len(external_duplicates)} "
        + f"codex_only={len(codex_only_entries)}"
    )

    if duplicate_entries:
        log(f"duplicate_names={','.join(duplicate_entries)}")

    if codex_only_entries:
        log(f"codex_only_names={','.join(codex_only_entries)}")

    if args.prune_duplicates and duplicate_entries:
        removed = 0
        for name in duplicate_entries:
            target = codex_skills / name
            if target.is_dir():
                shutil.rmtree(target)
                removed += 1
        log(f"pruned={removed}")
    elif duplicate_entries:
        log("pruned=0 (dry-run)")

    if codex_only_entries:
        log("codex_only_preserved=true")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
