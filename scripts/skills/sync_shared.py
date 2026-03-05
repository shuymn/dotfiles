#!/usr/bin/env python3
"""Sync the shared skill assets directory into ~/.agents/skills/_shared."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


IGNORE_NAMES = {".git", "__pycache__"}
LOG_PREFIX = "[skills:shared]"


def log(message: str) -> None:
    print(f"{LOG_PREFIX} {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync _shared skills assets")
    parser.add_argument("--source", required=True, help="Path to source _shared directory")
    parser.add_argument(
        "--destination",
        required=True,
        help="Path to destination _shared directory",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete destination before copy (mirror mode)",
    )
    return parser.parse_args()


def copy_shared(source: Path, destination: Path, delete_destination: bool) -> None:
    if not source.is_dir():
        raise SystemExit(f"Shared source directory does not exist: {source}")

    if destination.exists() and delete_destination:
        shutil.rmtree(destination)

    if destination.exists():
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns(*IGNORE_NAMES),
            copy_function=shutil.copy2,
            dirs_exist_ok=True,
        )
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns(*IGNORE_NAMES),
            copy_function=shutil.copy2,
        )


def main() -> int:
    args = parse_args()

    source = Path(args.source).expanduser().resolve()
    destination = Path(args.destination).expanduser().resolve()

    copy_shared(source, destination, args.delete)

    mode = "mirror" if args.delete else "merge"
    log(f"mode={mode} source={source} destination={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
