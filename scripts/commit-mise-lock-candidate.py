#!/usr/bin/env python3
"""Commit a validated mise.lock candidate through the GitHub Git Data API."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_API_URL = "https://api.github.com"
MAX_CANDIDATE_BYTES = 1024 * 1024
REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


class CommitError(RuntimeError):
    pass


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def load_attestation(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommitError(f"invalid attestation: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise CommitError("unsupported attestation schema")
    required_strings = ("base_sha", "head_sha", "head_ref", "lock_path", "lock_sha256")
    if not all(isinstance(data.get(key), str) for key in required_strings):
        raise CommitError("attestation string fields are invalid")
    if (
        type(data.get("repository_id")) is not int
        or type(data.get("pull_request")) is not int
        or data["repository_id"] <= 0
        or data["pull_request"] <= 0
    ):
        raise CommitError("attestation numeric fields are invalid")
    if not isinstance(data.get("changed_tools"), list) or not all(
        isinstance(tool, str) and tool for tool in data["changed_tools"]
    ):
        raise CommitError("attestation changed_tools is invalid")
    if not data["changed_tools"] or len(data["changed_tools"]) != len(
        set(data["changed_tools"])
    ):
        raise CommitError("attestation changed_tools must be non-empty and unique")
    if not SHA_PATTERN.fullmatch(data["base_sha"]) or not SHA_PATTERN.fullmatch(data["head_sha"]):
        raise CommitError("attestation contains invalid commit SHA")
    if data["lock_path"] != "home/dot_config/mise/mise.lock":
        raise CommitError("attestation contains unexpected lock path")
    if not data["head_ref"].startswith("renovate/") or len(data["head_ref"]) > 255:
        raise CommitError("attestation head must be a Renovate branch")
    if not re.fullmatch(r"[0-9a-f]{64}", data["lock_sha256"]):
        raise CommitError("attestation contains invalid lock digest")
    return data


class GitHubClient:
    def __init__(self, api_url: str, token: str) -> None:
        if api_url != DEFAULT_API_URL:
            parsed = urllib.parse.urlparse(api_url)
            if (
                os.environ.get("MISE_LOCK_ALLOW_INSECURE_API_FOR_TESTS") != "1"
                or parsed.scheme != "http"
                or parsed.hostname not in {"127.0.0.1", "localhost"}
            ):
                raise CommitError("custom API URL is allowed only for loopback tests")
        self.api_url = api_url.rstrip("/")
        self.token = token

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.api_url}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                error = json.loads(exc.read())
                message = error.get("message", "GitHub API request failed")
            except (json.JSONDecodeError, AttributeError):
                message = "GitHub API request failed"
            raise CommitError(f"GitHub API {method} {path} failed ({exc.code}): {message}") from exc
        except urllib.error.URLError as exc:
            raise CommitError(f"GitHub API request failed: {exc.reason}") from exc
        if not isinstance(data, dict):
            raise CommitError("GitHub API returned a non-object response")
        return data


def require_sha(data: dict[str, Any], *path: str) -> str:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            raise CommitError("GitHub API response is missing a SHA")
        value = value.get(key)
    if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
        raise CommitError("GitHub API response contains an invalid SHA")
    return value


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not REPOSITORY_PATTERN.fullmatch(args.repository):
        raise CommitError("invalid repository name")
    if not args.candidate.is_file() or args.candidate.stat().st_size > MAX_CANDIDATE_BYTES:
        raise CommitError("candidate must be a regular file within the size limit")

    attestation = load_attestation(args.attestation)
    candidate = args.candidate.read_bytes()
    if hashlib.sha256(candidate).hexdigest() != attestation["lock_sha256"]:
        raise CommitError("candidate digest does not match attestation")

    token = os.environ.get("MISE_LOCK_APP_TOKEN")
    if not token:
        raise CommitError("MISE_LOCK_APP_TOKEN is required")
    client = GitHubClient(args.api_url, token)
    repo_path = "/repos/" + args.repository
    repository = client.request("GET", repo_path)
    if repository.get("id") != attestation["repository_id"]:
        raise CommitError("repository ID does not match attestation")

    encoded_ref = urllib.parse.quote(attestation["head_ref"], safe="")
    ref_path = f"{repo_path}/git/ref/heads/{encoded_ref}"
    current_head = require_sha(client.request("GET", ref_path), "object", "sha")
    if current_head != attestation["head_sha"]:
        raise CommitError("pull request head changed after candidate validation")

    base_tree = require_sha(
        client.request("GET", f"{repo_path}/git/commits/{current_head}"), "tree", "sha"
    )
    blob = require_sha(
        client.request(
            "POST",
            f"{repo_path}/git/blobs",
            {"content": base64.b64encode(candidate).decode(), "encoding": "base64"},
        ),
        "sha",
    )
    tree = require_sha(
        client.request(
            "POST",
            f"{repo_path}/git/trees",
            {
                "base_tree": base_tree,
                "tree": [
                    {
                        "path": attestation["lock_path"],
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob,
                    }
                ],
            },
        ),
        "sha",
    )
    commit = require_sha(
        client.request(
            "POST",
            f"{repo_path}/git/commits",
            {
                "message": (
                    "Update mise.lock\n\n"
                    f"Source-PR: #{attestation['pull_request']}\n"
                    f"Source-Head: {current_head}"
                ),
                "tree": tree,
                "parents": [current_head],
            },
        ),
        "sha",
    )
    client.request(
        "PATCH",
        f"{repo_path}/git/refs/heads/{encoded_ref}",
        {"sha": commit, "force": False},
    )
    print(commit)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (CommitError, OSError) as exc:
        sys.stderr.write(f"mise lock commit rejected: {exc}\n")
        sys.exit(1)
