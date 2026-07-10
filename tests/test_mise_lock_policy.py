from __future__ import annotations

import unittest
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.mise_lock_policy import LockPolicyError, plan_update, verify_candidate, verify_lock


BASE_CONFIG = """\
[settings]
lockfile_platforms = ["macos-arm64", "linux-x64"]

[tools]
claude = "2.1.201"
node = "24.18.0"
"""

HEAD_CONFIG = BASE_CONFIG.replace('claude = "2.1.201"', 'claude = "2.1.205"')

BASE_LOCK = """\
[[tools.claude]]
version = "2.1.201"
backend = "aqua:anthropics/claude-code"

[[tools.node]]
version = "24.18.0"
backend = "core:node"
"""

CANDIDATE_LOCK = BASE_LOCK.replace('version = "2.1.201"', 'version = "2.1.205"', 1)

BASE_LOCK_WITH_PLATFORMS = """\
[[tools.claude]]
version = "2.1.201"
backend = "aqua:anthropics/claude-code"

[tools.claude."platforms.linux-x64"]
url = "https://example.com/2.1.201/linux"

[tools.claude."platforms.macos-arm64"]
url = "https://example.com/2.1.201/macos"

[[tools.node]]
version = "24.18.0"
backend = "core:node"
"""

CANDIDATE_LOCK_WITH_PLATFORMS = BASE_LOCK_WITH_PLATFORMS.replace(
    "2.1.201", "2.1.205"
)


class VerifyLockTests(unittest.TestCase):
    def test_accepts_lock_matching_configured_tool_versions(self) -> None:
        result = verify_lock(HEAD_CONFIG, CANDIDATE_LOCK)

        self.assertEqual(result.checked_tools, 2)

    def test_rejects_malformed_lock(self) -> None:
        with self.assertRaises(LockPolicyError):
            verify_lock(HEAD_CONFIG, "[[tools.claude")


class PlanUpdateTests(unittest.TestCase):
    def test_returns_changed_tools_and_configured_platforms(self) -> None:
        plan = plan_update(BASE_CONFIG, HEAD_CONFIG)

        self.assertEqual(plan.changed_tools, ("claude",))
        self.assertEqual(plan.platforms, ("macos-arm64", "linux-x64"))

    def test_rejects_tool_addition(self) -> None:
        head_config = HEAD_CONFIG + '\n"--help" = "9.9.9"\n'

        with self.assertRaisesRegex(LockPolicyError, "added or removed"):
            plan_update(BASE_CONFIG, head_config)


class VerifyCandidateTests(unittest.TestCase):
    def test_accepts_version_only_config_and_matching_lock_update(self) -> None:
        result = verify_candidate(BASE_CONFIG, HEAD_CONFIG, BASE_LOCK, CANDIDATE_LOCK)

        self.assertEqual(result.changed_tools, ("claude",))

    def test_rejects_non_version_config_changes(self) -> None:
        head_config = HEAD_CONFIG.replace(
            'claude = "2.1.205"',
            'claude = { version = "2.1.205", postinstall = "unsafe" }',
        )

        with self.assertRaisesRegex(LockPolicyError, "option change"):
            verify_candidate(BASE_CONFIG, head_config, BASE_LOCK, CANDIDATE_LOCK)

    def test_rejects_lock_changes_outside_tool_sections(self) -> None:
        candidate = 'metadata = "tampered"\n' + CANDIDATE_LOCK

        with self.assertRaisesRegex(LockPolicyError, "outside tool sections"):
            verify_candidate(BASE_CONFIG, HEAD_CONFIG, BASE_LOCK, candidate)

    def test_rejects_extra_versions_in_changed_lock_section(self) -> None:
        candidate = CANDIDATE_LOCK.replace(
            '[[tools.node]]',
            '[[tools.claude]]\nversion = "9.9.9"\nbackend = "aqua:anthropics/claude-code"\n\n[[tools.node]]',
        )

        with self.assertRaisesRegex(LockPolicyError, "section order|version mismatch"):
            verify_candidate(BASE_CONFIG, HEAD_CONFIG, BASE_LOCK, candidate)

    def test_rejects_backend_change_in_changed_lock_section(self) -> None:
        candidate = CANDIDATE_LOCK.replace(
            "aqua:anthropics/claude-code", "http:attacker-controlled"
        )

        with self.assertRaisesRegex(LockPolicyError, "backend"):
            verify_candidate(BASE_CONFIG, HEAD_CONFIG, BASE_LOCK, candidate)

    def test_rejects_missing_configured_platform(self) -> None:
        candidate = CANDIDATE_LOCK_WITH_PLATFORMS.replace(
            '[tools.claude."platforms.macos-arm64"]\n'
            'url = "https://example.com/2.1.205/macos"\n\n',
            "",
        )

        with self.assertRaisesRegex(LockPolicyError, "platform"):
            verify_candidate(
                BASE_CONFIG,
                HEAD_CONFIG,
                BASE_LOCK_WITH_PLATFORMS,
                candidate,
            )

    def test_rejects_textual_changes_outside_changed_sections(self) -> None:
        candidate = "# untrusted preamble change\n" + CANDIDATE_LOCK

        with self.assertRaisesRegex(LockPolicyError, "preamble"):
            verify_candidate(BASE_CONFIG, HEAD_CONFIG, BASE_LOCK, candidate)

    def test_rejects_candidate_when_unchanged_lock_entry_is_stale(self) -> None:
        stale_base_lock = BASE_LOCK.replace('version = "24.18.0"', 'version = "24.17.0"')
        candidate = stale_base_lock.replace('version = "2.1.201"', 'version = "2.1.205"')

        with self.assertRaisesRegex(LockPolicyError, "version mismatch: node"):
            verify_candidate(BASE_CONFIG, HEAD_CONFIG, stale_base_lock, candidate)


class VerifyCandidateCliTests(unittest.TestCase):
    def test_writes_attestation_for_exact_git_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            config = repo / "home/dot_config/mise/config.toml"
            lock = repo / "home/dot_config/mise/mise.lock"
            config.parent.mkdir(parents=True)
            config.write_text(BASE_CONFIG)
            lock.write_text(BASE_LOCK)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
            base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            config.write_text(HEAD_CONFIG)
            subprocess.run(["git", "commit", "-qam", "head"], cwd=repo, check=True)
            head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            candidate = Path(temp_dir) / "candidate.lock"
            attestation = Path(temp_dir) / "attestation.json"
            candidate.write_text(CANDIDATE_LOCK)

            subprocess.run(
                [
                    sys.executable,
                    "scripts/verify-mise-lock-candidate.py",
                    "--repo",
                    str(repo),
                    "--base",
                    base_sha,
                    "--head",
                    head_sha,
                    "--candidate",
                    str(candidate),
                    "--repository-id",
                    "31846381",
                    "--pull-request",
                    "42",
                    "--head-ref",
                    "renovate/claude",
                    "--output",
                    str(attestation),
                ],
                cwd=Path(__file__).parents[1],
                check=True,
            )

            data = json.loads(attestation.read_text())
            self.assertEqual(data["head_sha"], head_sha)
            self.assertEqual(data["changed_tools"], ["claude"])


if __name__ == "__main__":
    unittest.main()
