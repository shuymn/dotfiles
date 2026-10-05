#!/usr/bin/env python3
"""Update mise tools to releases past the minimum age and regenerate mise.lock.

The scheduled mise update workflow runs this on a default-branch checkout
without write credentials. Versions stay within their current major line;
major updates and releases without timestamps are reported instead.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mise_update_policy import (
    Decision,
    Hold,
    Release,
    UpdatePolicyError,
    configured_versions,
    parse_timestamp,
    parse_version,
    releases_from_metadata,
    render_report,
    replace_version,
    select_update,
)

CONFIG_PATH = "home/dot_config/mise/config.toml"
MINIMUM_AGE = timedelta(days=1)
LOCK_UPDATER = Path(__file__).with_name("update-mise-lock-for-changed-tools.py")
# mise reports no timestamps for core:go; the Go module proxy records when each
# toolchain release was published.
GO_TOOLCHAIN_INFO = "https://proxy.golang.org/golang.org/toolchain/@v/v0.0.1-go{version}.linux-amd64.info"


def fetch_releases(tool: str) -> list[Release]:
    completed = subprocess.run(
        ["mise", "ls-remote", "--json", "--no-versions-host", "--strict-metadata", tool],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return releases_from_metadata(json.loads(completed.stdout))


def go_release_time(version: str) -> datetime | None:
    try:
        with urllib.request.urlopen(GO_TOOLCHAIN_INFO.format(version=version), timeout=30) as response:
            info = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            return None
        raise
    return parse_timestamp(info.get("Time") if isinstance(info, dict) else None)


def with_go_release_times(releases: list[Release], current: str) -> list[Release]:
    floor = parse_version(current)
    result = []
    for release in releases:
        key = parse_version(release.version)
        if release.created_at is None and key is not None and floor is not None and key >= floor:
            release = replace(release, created_at=go_release_time(release.version))
        result.append(release)
    return result


def evaluate(tool: str, current: str, now: datetime, minimum_age: timedelta) -> Decision:
    releases = fetch_releases(tool)
    if tool == "go":
        releases = with_go_release_times(releases, current)
    if not any(release.created_at for release in releases):
        raise UpdatePolicyError("no release timestamps available")
    return select_update(tool, current, releases, now=now, minimum_age=minimum_age)


def error_detail(exc: Exception) -> str:
    if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
        return exc.stderr.strip().splitlines()[-1]
    return str(exc)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(CONFIG_PATH))
    parser.add_argument("--dry-run", action="store_true", help="report updates without changing files")
    parser.add_argument("--report", type=Path, help="write the Markdown report here instead of stdout")
    parser.add_argument(
        "--source", default="the current checkout", help="describe the base in the report"
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        original = args.config.read_text(encoding="utf-8")
        versions, unsupported = configured_versions(original)
    except (OSError, UpdatePolicyError) as exc:
        print(exc, file=sys.stderr)
        return 1

    now = datetime.now(UTC)
    decisions = [
        Decision(name, "-", None, (Hold("-", "only plain string versions are updated"),))
        for name in unsupported
    ]
    errors = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            tool: pool.submit(evaluate, tool, current, now, MINIMUM_AGE)
            for tool, current in versions.items()
        }
    for tool, future in futures.items():
        try:
            decisions.append(future.result())
        except (subprocess.CalledProcessError, OSError, ValueError) as exc:
            errors.append(f"{tool}: {error_detail(exc)}")

    report = render_report(decisions, source=args.source)
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    if errors:
        print("failed to evaluate mise tools:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1

    updates = [decision for decision in decisions if decision.target is not None]
    if args.dry_run or not updates:
        return 0

    updated = original
    try:
        for decision in updates:
            assert decision.target is not None
            updated = replace_version(updated, decision.tool, decision.current, decision.target.version)
    except UpdatePolicyError as exc:
        print(exc, file=sys.stderr)
        return 1
    args.config.write_text(updated, encoding="utf-8")
    return subprocess.run([sys.executable, str(LOCK_UPDATER), "--base", "HEAD"]).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
