#!/usr/bin/env python3
"""CLI adapter for repository mise lock validation."""

from __future__ import annotations

import sys
from pathlib import Path

from mise_lock_policy import LockPolicyError, verify_lock


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LockPolicyError(f"failed to read {path}: {exc}") from exc


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(f"usage: {argv[0]} mise-config.toml mise.lock\n")
        return 2

    try:
        validation = verify_lock(read_text(Path(argv[1])), read_text(Path(argv[2])))
    except LockPolicyError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    print(f"mise lock consistency check passed ({validation.checked_tools} tools)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
