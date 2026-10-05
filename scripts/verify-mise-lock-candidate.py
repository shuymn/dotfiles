#!/usr/bin/env python3
"""Verify an untrusted mise config and lock candidate against trusted base files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mise_lock_policy import LockPolicyError, verify_candidate
from mise_update_policy import UpdatePolicyError, render_pull_request, validated_changes


MAX_CANDIDATE_BYTES = 1024 * 1024


class Abort(ValueError):
    pass


def read_candidate(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise Abort(f"{path.name} must be a regular file")
    if path.stat().st_size > MAX_CANDIDATE_BYTES:
        raise Abort(f"{path.name} exceeds size limit")
    return path.read_text(encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--base-lock", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--run-url", required=True, help="workflow run linked from the PR body")
    parser.add_argument("--title-out", type=Path, required=True)
    parser.add_argument("--body-out", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    base_config = args.base_config.read_text(encoding="utf-8")
    head_config = read_candidate(args.config)
    verify_candidate(
        base_config,
        head_config,
        args.base_lock.read_text(encoding="utf-8"),
        read_candidate(args.candidate),
    )
    title, body = render_pull_request(
        validated_changes(base_config, head_config), run_url=args.run_url
    )
    args.title_out.write_text(title + "\n", encoding="utf-8")
    args.body_out.write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (Abort, LockPolicyError, UpdatePolicyError, OSError) as exc:
        sys.stderr.write(f"mise update candidate rejected: {exc}\n")
        sys.exit(1)
