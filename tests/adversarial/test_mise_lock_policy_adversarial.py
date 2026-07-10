from __future__ import annotations

import unittest

from scripts.mise_lock_policy import (
    LockPolicyError,
    plan_update,
    verify_candidate,
    verify_lock,
)


BASE_CONFIG = """\
[settings]
lockfile_platforms = ["macos-arm64", "linux-x64"]

[tools]
claude = "2.1.201"
"""

HEAD_CONFIG = BASE_CONFIG.replace("2.1.201", "2.1.205")

BASE_LOCK = """\
[[tools.claude]]
version = "2.1.201"
backend = "aqua:anthropics/claude-code"
"""

CANDIDATE_LOCK = BASE_LOCK.replace("2.1.201", "2.1.205")


class MiseLockPolicyAdversarialTests(unittest.TestCase):
    def test_rejects_empty_or_truncated_documents(self) -> None:
        for config, lock in (("", CANDIDATE_LOCK), (HEAD_CONFIG, "[[tools.claude")):
            with self.subTest(config=config, lock=lock):
                with self.assertRaises(LockPolicyError):
                    verify_lock(config, lock)

    def test_rejects_tool_and_backend_injection(self) -> None:
        injected_config = HEAD_CONFIG + '\n"--help" = "9.9.9"\n'
        with self.assertRaisesRegex(LockPolicyError, "added or removed"):
            plan_update(BASE_CONFIG, injected_config)

        injected_lock = CANDIDATE_LOCK.replace(
            "aqua:anthropics/claude-code",
            "http:../../attacker-controlled",
        )
        with self.assertRaisesRegex(LockPolicyError, "backend"):
            verify_candidate(BASE_CONFIG, HEAD_CONFIG, BASE_LOCK, injected_lock)


if __name__ == "__main__":
    unittest.main()
