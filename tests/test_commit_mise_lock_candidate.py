from __future__ import annotations

import hashlib
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path


HEAD_SHA = "a" * 40
BASE_TREE_SHA = "b" * 40
BLOB_SHA = "c" * 40
TREE_SHA = "d" * 40
COMMIT_SHA = "e" * 40


class GitHubApiHandler(http.server.BaseHTTPRequestHandler):
    requests: list[tuple[str, str, dict[str, object] | None]] = []

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _respond(self, status: int, data: dict[str, object]) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, object] | None:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length)) if length else None

    def do_GET(self) -> None:
        self.requests.append(("GET", self.path, None))
        if self.path == "/repos/shuymn/dotfiles":
            self._respond(200, {"id": 31846381})
        elif self.path.endswith("/git/ref/heads/renovate%2Fclaude"):
            self._respond(200, {"object": {"sha": HEAD_SHA}})
        elif self.path.endswith(f"/git/commits/{HEAD_SHA}"):
            self._respond(200, {"tree": {"sha": BASE_TREE_SHA}})
        else:
            self._respond(404, {"message": "not found"})

    def do_POST(self) -> None:
        body = self._body()
        self.requests.append(("POST", self.path, body))
        if self.path.endswith("/git/blobs"):
            self._respond(201, {"sha": BLOB_SHA})
        elif self.path.endswith("/git/trees"):
            self._respond(201, {"sha": TREE_SHA})
        elif self.path.endswith("/git/commits"):
            self._respond(201, {"sha": COMMIT_SHA})
        else:
            self._respond(404, {"message": "not found"})

    def do_PATCH(self) -> None:
        body = self._body()
        self.requests.append(("PATCH", self.path, body))
        self._respond(200, {"object": {"sha": COMMIT_SHA}})


class CommitCandidateCliTests(unittest.TestCase):
    def test_rejects_candidate_digest_mismatch_before_api_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate = root / "mise.lock"
            attestation = root / "attestation.json"
            candidate.write_text('[[tools.claude]]\nversion = "tampered"\n')
            attestation.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "repository_id": 31846381,
                        "pull_request": 160,
                        "base_sha": "f" * 40,
                        "head_sha": HEAD_SHA,
                        "head_ref": "renovate/claude",
                        "lock_path": "home/dot_config/mise/mise.lock",
                        "lock_sha256": "0" * 64,
                        "changed_tools": ["claude"],
                    }
                )
                + "\n"
            )
            env = os.environ | {
                "MISE_LOCK_APP_TOKEN": "test-token",
                "MISE_LOCK_ALLOW_INSECURE_API_FOR_TESTS": "1",
            }

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/commit-mise-lock-candidate.py",
                    "--repository",
                    "shuymn/dotfiles",
                    "--candidate",
                    str(candidate),
                    "--attestation",
                    str(attestation),
                    "--api-url",
                    "http://127.0.0.1:9",
                ],
                cwd=Path(__file__).parents[1],
                env=env,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("digest does not match", result.stderr)

    def test_rejects_attestation_for_non_renovate_branch_before_api_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate = root / "mise.lock"
            attestation = root / "attestation.json"
            candidate.write_text('[[tools.claude]]\nversion = "2.1.205"\n')
            attestation.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "repository_id": 31846381,
                        "pull_request": 160,
                        "base_sha": "f" * 40,
                        "head_sha": HEAD_SHA,
                        "head_ref": "feature/untrusted",
                        "lock_path": "home/dot_config/mise/mise.lock",
                        "lock_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                        "changed_tools": ["claude"],
                    }
                )
                + "\n"
            )
            env = os.environ | {
                "MISE_LOCK_APP_TOKEN": "test-token",
                "MISE_LOCK_ALLOW_INSECURE_API_FOR_TESTS": "1",
            }

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/commit-mise-lock-candidate.py",
                    "--repository",
                    "shuymn/dotfiles",
                    "--candidate",
                    str(candidate),
                    "--attestation",
                    str(attestation),
                    "--api-url",
                    "http://127.0.0.1:9",
                ],
                cwd=Path(__file__).parents[1],
                env=env,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Renovate branch", result.stderr)

    def test_commits_validated_lock_with_non_force_ref_update(self) -> None:
        GitHubApiHandler.requests = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), GitHubApiHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate = root / "mise.lock"
            attestation = root / "attestation.json"
            candidate.write_text('[[tools.claude]]\nversion = "2.1.205"\n')
            attestation.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "repository_id": 31846381,
                        "pull_request": 160,
                        "base_sha": "f" * 40,
                        "head_sha": HEAD_SHA,
                        "head_ref": "renovate/claude",
                        "lock_path": "home/dot_config/mise/mise.lock",
                        "lock_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                        "changed_tools": ["claude"],
                    }
                )
                + "\n"
            )
            env = os.environ | {
                "MISE_LOCK_APP_TOKEN": "test-token",
                "MISE_LOCK_ALLOW_INSECURE_API_FOR_TESTS": "1",
            }

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/commit-mise-lock-candidate.py",
                    "--repository",
                    "shuymn/dotfiles",
                    "--candidate",
                    str(candidate),
                    "--attestation",
                    str(attestation),
                    "--api-url",
                    f"http://127.0.0.1:{server.server_port}",
                ],
                cwd=Path(__file__).parents[1],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.stdout.strip(), COMMIT_SHA)
        method, _, body = GitHubApiHandler.requests[-1]
        self.assertEqual(method, "PATCH")
        self.assertEqual(body, {"sha": COMMIT_SHA, "force": False})

    def test_rejects_stale_head_before_any_write_request(self) -> None:
        GitHubApiHandler.requests = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), GitHubApiHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate = root / "mise.lock"
            attestation = root / "attestation.json"
            candidate.write_text('[[tools.claude]]\nversion = "2.1.205"\n')
            attestation.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "repository_id": 31846381,
                        "pull_request": 160,
                        "base_sha": "f" * 40,
                        "head_sha": "9" * 40,
                        "head_ref": "renovate/claude",
                        "lock_path": "home/dot_config/mise/mise.lock",
                        "lock_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                        "changed_tools": ["claude"],
                    }
                )
                + "\n"
            )
            env = os.environ | {
                "MISE_LOCK_APP_TOKEN": "test-token",
                "MISE_LOCK_ALLOW_INSECURE_API_FOR_TESTS": "1",
            }

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/commit-mise-lock-candidate.py",
                    "--repository",
                    "shuymn/dotfiles",
                    "--candidate",
                    str(candidate),
                    "--attestation",
                    str(attestation),
                    "--api-url",
                    f"http://127.0.0.1:{server.server_port}",
                ],
                cwd=Path(__file__).parents[1],
                env=env,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("head changed", result.stderr)
        self.assertFalse(any(method in {"POST", "PATCH"} for method, _, _ in GitHubApiHandler.requests))


if __name__ == "__main__":
    unittest.main()
