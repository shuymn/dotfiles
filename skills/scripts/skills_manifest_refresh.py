#!/usr/bin/env python3
"""Refresh the dotfiles-managed skills manifest from a local skills source."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
COMMON_LIB_DIR = SCRIPT_DIR.parent / "src" / "common" / "scripts" / "lib"
if str(COMMON_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_LIB_DIR))

from skills_models import ManagedSkillsManifestModel  # noqa: E402

MANIFEST_VERSION = 1
DEFAULT_MANIFEST_NAME = ".dotfiles-managed-skills.json"
SKILL_FILE_NAME = "SKILL.md"
LOG_PREFIX = "[skills:manifest]"


def log(message: str) -> None:
    print(f"{LOG_PREFIX} {message}")


def sanitize_name(name: str) -> str:
    """Match the skills CLI sanitize rule for directory names."""
    sanitized = re.sub(r"[^a-z0-9._]+", "-", name.lower())
    sanitized = re.sub(r"^[.-]+|[.-]+$", "", sanitized)
    return sanitized[:255] or "unnamed-skill"


def discover_skills(source_root: Path) -> list[str]:
    """Discover direct child skill directories that contain SKILL.md."""
    names: list[str] = []

    for child in sorted(source_root.iterdir()):
        if not child.is_dir():
            continue
        if (child / SKILL_FILE_NAME).is_file():
            names.append(sanitize_name(child.name))

    return sorted(set(names))


def format_source_root_for_manifest(source_root: Path, manifest_path: Path) -> str:
    """Return a machine-independent source_root string for manifest output."""
    relative = Path(os.path.relpath(source_root, manifest_path.parent))
    return "." if str(relative) == "." else relative.as_posix()


def build_manifest(source_root: str, skills: list[str]) -> dict[str, object]:
    return ManagedSkillsManifestModel(
        version=MANIFEST_VERSION,
        source_root=str(source_root),
        skills=skills,
    ).model_dump(mode="json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh dotfiles-managed skills manifest"
    )
    parser.add_argument(
        "--source", required=True, help="Path to the local skills source root"
    )
    parser.add_argument(
        "--manifest",
        help="Manifest output path (default: <source>/.dotfiles-managed-skills.json)",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the generated manifest instead of writing it",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    source_root = Path(args.source).expanduser().resolve()
    if not source_root.is_dir():
        raise SystemExit(f"Source skills directory does not exist: {source_root}")

    manifest_path = (
        Path(args.manifest).expanduser().resolve()
        if args.manifest
        else source_root / DEFAULT_MANIFEST_NAME
    )

    skills = discover_skills(source_root)
    manifest_source_root = format_source_root_for_manifest(source_root, manifest_path)
    manifest = build_manifest(manifest_source_root, skills)

    if args.print_only:
        print(json.dumps(manifest, indent=2))
        return 0

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    log(f"manifest_path={manifest_path}")
    log(f"managed_skills={len(skills)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
