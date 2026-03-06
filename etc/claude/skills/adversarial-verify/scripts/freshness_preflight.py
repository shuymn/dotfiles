#!/usr/bin/env python3
"""Pre-flight digest freshness check for review/recheck artifacts.

Usage:
  uv run python freshness_preflight.py <topic-dir>

Scans <topic-dir> for all review/recheck/adversarial artifacts
(*.review.md, *.dod-recheck.md, *.adversarial.md), extracts their
Source Digest and Source Artifact metadata, and verifies the current
SHA-256 of each source file matches the stored digest.

Stale artifacts indicate that the source changed after the review —
downstream skills will fail gate-check.sh. Running this preflight
early prevents wasted work.

Output: LLM_CHECK_V2 format (via shared llm_check helper).
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from llm_check import emit_footer, emit_header, emit_line, resolve_mode  # noqa: E402

TOOL_NAME = "freshness-preflight"

_ARTIFACT_GLOB_PATTERNS = (
    "*.review.md",
    "*.dod-recheck.md",
    "*.adversarial.md",
)

_DIGEST_RE = re.compile(
    r"Source Digest\*{0,2}\s*:\s*([a-f0-9]{64})",
    re.IGNORECASE,
)
_ARTIFACT_RE = re.compile(
    r"Source Artifact\*{0,2}\s*:\s*(.+?)(?:\s*$|\s*\n)",
    re.IGNORECASE | re.MULTILINE,
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _find_artifact_files(topic_dir: Path) -> list[Path]:
    found: list[Path] = []
    for pattern in _ARTIFACT_GLOB_PATTERNS:
        found.extend(sorted(topic_dir.glob(pattern)))
    return found


def _extract_metadata(text: str) -> tuple[str, str]:
    """Return (source_digest, source_artifact_path) from artifact text."""
    digest_m = _DIGEST_RE.search(text)
    artifact_m = _ARTIFACT_RE.search(text)
    digest = digest_m.group(1).strip() if digest_m else ""
    artifact = artifact_m.group(1).strip() if artifact_m else ""
    return digest, artifact


def check_artifact(artifact_path: Path, base_dir: Path) -> tuple[str, str, str]:
    """Return (status, artifact_name, issue). status: PASS | STALE | SKIP."""
    text = artifact_path.read_text(encoding="utf-8")
    stored_digest, source_artifact = _extract_metadata(text)
    name = artifact_path.name

    if not stored_digest:
        return ("SKIP", name, "no Source Digest found in artifact")

    if not source_artifact:
        return ("SKIP", name, "no Source Artifact path found in artifact")

    # Resolve source artifact path (repository-relative or absolute)
    source_path = Path(source_artifact)
    if not source_path.is_absolute():
        # Try relative to base_dir first, then to artifact's parent
        candidate = base_dir / source_path
        if not candidate.exists():
            candidate = artifact_path.parent / source_path
        source_path = candidate

    if not source_path.exists():
        return ("SKIP", name, f"source file not found: {source_artifact}")

    current_digest = _sha256(source_path)
    if current_digest != stored_digest:
        return (
            "STALE",
            name,
            f"digest mismatch: stored={stored_digest[:12]}... current={current_digest[:12]}..."
            f" (source: {source_artifact})",
        )

    return ("PASS", name, "")


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Pre-flight digest freshness check for review/recheck artifacts"
    )
    parser.add_argument("topic_dir", help="Path to topic directory (e.g., docs/plans/<topic>/)")
    parser.add_argument(
        "--base-dir",
        default="",
        help="Repository root for resolving relative source paths (default: topic_dir parent)",
    )
    args = parser.parse_args(argv[1:])

    mode = resolve_mode()
    topic_dir = Path(args.topic_dir)
    base_dir = Path(args.base_dir) if args.base_dir else topic_dir.parent.parent

    if not topic_dir.exists() or not topic_dir.is_dir():
        emit_header(
            TOOL_NAME, mode, "FAIL", "TOPIC_DIR_NOT_FOUND",
            f"Topic directory not found: {topic_dir}",
        )
        emit_line("fix.1", "FIX_TOPIC_DIR_PATH")
        emit_footer()
        return 1

    artifact_files = _find_artifact_files(topic_dir)

    if not artifact_files:
        emit_header(
            TOOL_NAME, mode, "SKIP", "NO_REVIEW_ARTIFACTS",
            f"No review/recheck/adversarial artifacts found in {topic_dir}.",
        )
        emit_footer()
        return 0

    stale: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    passed = 0

    for af in artifact_files:
        status, name, issue = check_artifact(af, base_dir)
        if status == "STALE":
            stale.append((name, issue))
        elif status == "SKIP":
            skipped.append((name, issue))
        else:
            passed += 1

    overall = "FAIL" if stale else "PASS"
    code = "STALE_REVIEW_ARTIFACTS" if stale else "ALL_ARTIFACTS_FRESH"
    summary = (
        f"{len(stale)} artifact(s) are stale (source changed after review)."
        if stale
        else f"All {passed} artifact(s) are fresh."
    )

    emit_header(TOOL_NAME, mode, overall, code, summary)
    emit_line("signal.total_artifacts", len(artifact_files))
    emit_line("signal.passed", passed)
    emit_line("signal.stale", len(stale))
    emit_line("signal.skipped", len(skipped))

    for i, (name, issue) in enumerate(stale, 1):
        emit_line(f"stale.{i}", f"{name}: {issue}")
    for i, (name, issue) in enumerate(skipped, 1):
        emit_line(f"skip.{i}", f"{name}: {issue}")

    if stale:
        emit_line("fix.1", "FIX_RERUN_REVIEW_ON_CURRENT_SOURCE")
        emit_line("fix.2", "FIX_UPDATE_SOURCE_DIGEST_IN_ARTIFACT")

    emit_footer()
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
