from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "gh-api-retry.sh"


class GhApiRetryTests(unittest.TestCase):
    def run_helper(
        self,
        gh_body: str,
        *args: str,
        extra_env: dict[str, str] | None = None,
        mock_date: int | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], list[str], list[str], str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            state = root / "state"
            gh_log = root / "gh.log"
            sleep_log = root / "sleep.log"

            gh = bin_dir / "gh"
            gh.write_text(
                "#!/bin/sh\n"
                "set -eu\n"
                'printf "%s\\n" "$*" >>"$MOCK_GH_LOG"\n'
                + textwrap.dedent(gh_body),
                encoding="utf-8",
            )
            gh.chmod(0o755)

            sleep = bin_dir / "sleep"
            sleep.write_text(
                "#!/bin/sh\n"
                "set -eu\n"
                'printf "%s\\n" "$1" >>"$MOCK_SLEEP_LOG"\n',
                encoding="utf-8",
            )
            sleep.chmod(0o755)

            if mock_date is not None:
                date = bin_dir / "date"
                date.write_text(
                    f"#!/bin/sh\nprintf '%s\\n' {mock_date}\n",
                    encoding="utf-8",
                )
                date.chmod(0o755)

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
                    "MOCK_GH_LOG": str(gh_log),
                    "MOCK_SLEEP_LOG": str(sleep_log),
                    "MOCK_STATE": str(state),
                }
            )
            if extra_env:
                env.update(extra_env)

            result = subprocess.run(
                ["/bin/sh", str(SCRIPT), *args],
                cwd=REPO,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            sleeps = sleep_log.read_text().splitlines() if sleep_log.exists() else []
            calls = gh_log.read_text().splitlines() if gh_log.exists() else []
            attempts = state.read_text().strip() if state.exists() else ""
            return result, sleeps, calls, attempts

    def test_forwards_successful_zero_result_and_preserves_arguments(self) -> None:
        result, sleeps, calls, _ = self.run_helper(
            "printf '0\\n'\n",
            "repos/owner/repo/actions/runs/1/artifacts",
            "--jq",
            ".total_count",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "0\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(sleeps, [])
        self.assertEqual(
            calls,
            [
                "api repos/owner/repo/actions/runs/1/artifacts "
                "--jq .total_count"
            ],
        )

    def test_retries_transient_errors_without_forwarding_failed_stdout(self) -> None:
        gh_body = r"""
            if [ "$2" = rate_limit ]; then
              exit 0
            fi
            attempt=0
            if [ -f "$MOCK_STATE" ]; then attempt=$(cat "$MOCK_STATE"); fi
            attempt=$((attempt + 1))
            printf '%s\n' "$attempt" >"$MOCK_STATE"
            if [ "$attempt" -eq 1 ]; then
              printf 'partial failed response\n'
              printf '%s\n' "$MOCK_ERROR" >&2
              exit 7
            fi
            printf 'payload\n'
        """
        cases = (
            (
                "gh: API rate limit exceeded for installation ID 1. "
                "(HTTP 403)",
                "60",
            ),
            ("gh: Too many requests (HTTP 429)", "60"),
            ("gh: HTTP 429", "60"),
            ("gh: upstream failure (HTTP 599)", "5"),
            ("gh: HTTP 502", "5"),
            ("gh: error connecting to api.github.com", "5"),
        )
        for error, expected_delay in cases:
            with self.subTest(error=error):
                result, sleeps, _, attempts = self.run_helper(
                    gh_body,
                    "repos/owner/repo/pulls/1",
                    extra_env={"MOCK_ERROR": error},
                )

                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "payload\n")
                self.assertNotIn("partial failed response", result.stdout)
                self.assertEqual(sleeps, [expected_delay])
                self.assertEqual(attempts, "2")

    def test_fails_non_rate_limit_403_without_retry(self) -> None:
        gh_body = r"""
            printf '1\n' >"$MOCK_STATE"
            printf 'partial failed response\n'
            echo 'gh: Resource not accessible by integration (HTTP 403)' >&2
            exit 9
        """
        result, sleeps, calls, attempts = self.run_helper(
            gh_body,
            "repos/owner/repo/pulls/1",
        )

        self.assertEqual(result.returncode, 9)
        self.assertEqual(result.stdout, "")
        self.assertEqual(sleeps, [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(attempts, "1")

    def test_stops_after_six_transient_attempts(self) -> None:
        gh_body = r"""
            attempt=0
            if [ -f "$MOCK_STATE" ]; then attempt=$(cat "$MOCK_STATE"); fi
            attempt=$((attempt + 1))
            printf '%s\n' "$attempt" >"$MOCK_STATE"
            echo 'gh: upstream failure (HTTP 503)' >&2
            exit 42
        """
        result, sleeps, _, attempts = self.run_helper(
            gh_body,
            "repos/owner/repo/pulls/1",
        )

        self.assertEqual(result.returncode, 42)
        self.assertEqual(result.stdout, "")
        self.assertEqual(sleeps, ["5", "10", "15", "20", "25"])
        self.assertEqual(attempts, "6")

    def test_caps_rate_limit_waits_at_ten_minutes_total(self) -> None:
        gh_body = r"""
            if [ "$2" = rate_limit ]; then
              printf '9999\n'
              exit 0
            fi
            attempt=0
            if [ -f "$MOCK_STATE" ]; then attempt=$(cat "$MOCK_STATE"); fi
            attempt=$((attempt + 1))
            printf '%s\n' "$attempt" >"$MOCK_STATE"
            echo 'gh: API rate limit exceeded for installation ID 1 (HTTP 403)' >&2
            exit 13
        """
        result, sleeps, calls, attempts = self.run_helper(
            gh_body,
            "repos/owner/repo/pulls/1",
            mock_date=100,
        )

        self.assertEqual(result.returncode, 13)
        self.assertEqual(sleeps, ["300", "300"])
        self.assertEqual(attempts, "3")
        self.assertEqual(sum(call.startswith("api rate_limit ") for call in calls), 2)

    def test_rejects_missing_endpoint_and_non_get_forms(self) -> None:
        cases = (
            (),
            ("--jq", ".total_count"),
            ("graphql",),
            ("repos/owner/repo", "--input", "request.json"),
            ("repos/owner/repo", "-X", "POST"),
            ("repos/owner/repo", "-f", "key=value"),
        )
        for args in cases:
            with self.subTest(args=args):
                result, sleeps, calls, _ = self.run_helper(
                    "echo should-not-run >&2\nexit 99\n",
                    *args,
                )

                self.assertEqual(result.returncode, 2)
                self.assertEqual(sleeps, [])
                self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
