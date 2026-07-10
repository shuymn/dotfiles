#!/usr/bin/env python3
"""Verify an untrusted mise.lock candidate and emit a bound attestation."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from mise_lock_candidate import CandidateError, verify_candidate


CONFIG_PATH = "home/dot_config/mise/config.toml"
LOCK_PATH = "home/dot_config/mise/mise.lock"
MAX_CANDIDATE_BYTES = 1024 * 1024
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def git_show(repo: Path, sha: str, path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{sha}:{path}"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--repository-id", type=int, required=True)
    parser.add_argument("--pull-request", type=int, required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not SHA_PATTERN.fullmatch(args.base) or not SHA_PATTERN.fullmatch(args.head):
        raise CandidateError("base and head must be full commit SHAs")
    if args.repository_id <= 0 or args.pull_request <= 0:
        raise CandidateError("repository and pull request IDs must be positive")
    if not args.head_ref or len(args.head_ref) > 255:
        raise CandidateError("invalid head ref")
    if not args.candidate.is_file():
        raise CandidateError("candidate must be a regular file")
    if args.candidate.stat().st_size > MAX_CANDIDATE_BYTES:
        raise CandidateError("candidate exceeds size limit")

    candidate_text = args.candidate.read_text(encoding="utf-8")
    validation = verify_candidate(
        git_show(args.repo, args.base, CONFIG_PATH),
        git_show(args.repo, args.head, CONFIG_PATH),
        git_show(args.repo, args.base, LOCK_PATH),
        candidate_text,
    )
    attestation = {
        "schema": 1,
        "repository_id": args.repository_id,
        "pull_request": args.pull_request,
        "base_sha": args.base,
        "head_sha": args.head,
        "head_ref": args.head_ref,
        "lock_path": LOCK_PATH,
        "lock_sha256": validation.sha256,
        "changed_tools": list(validation.changed_tools),
    }
    args.output.write_text(json.dumps(attestation, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (CandidateError, OSError, subprocess.CalledProcessError) as exc:
        sys.stderr.write(f"mise lock candidate rejected: {exc}\n")
        sys.exit(1)
