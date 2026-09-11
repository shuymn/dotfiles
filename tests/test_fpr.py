from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home" / "dot_local" / "private_bin" / "executable_fpr"


class FprTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.work = self.root / "work"
        self.github = self.root / "github.git"
        self.forgejo_root = self.root / "forgejo"
        self.state = self.root / "mock-state"
        self.curl_log = self.root / "curl.log"
        self.git_env_log = self.root / "git-env.log"
        self.git_args_log = self.root / "git-args.log"
        self.host_key = "AAAAC3NzaC1lZDI1NTE5AAAAIE5ENGikTM8UWMFm81ZHOaHXTw9CPYu+4CLf1gDHp03X"
        self.real_git = shutil.which("git")
        assert self.real_git is not None
        self.bin.mkdir()
        self.home.mkdir()
        self.forgejo_root.mkdir()
        self.state.mkdir()

        self.env = os.environ.copy()
        self.env.update(
            {
                "HOME": str(self.home),
                "PATH": f"{self.bin}{os.pathsep}{self.env['PATH']}",
                "GIT_CONFIG_NOSYSTEM": "1",
                "FPR_CONFIG_FILE": str(self.root / "fpr-config"),
                "MOCK_STATE": str(self.state),
                "MOCK_CURL_LOG": str(self.curl_log),
                "MOCK_GIT_ENV_LOG": str(self.git_env_log),
                "MOCK_GIT_ARGS_LOG": str(self.git_args_log),
                "MOCK_FORCE_SHALLOW": "0",
                "REAL_GIT": self.real_git,
                "MOCK_REPO_EXISTS": "1",
                "MOCK_APPROVAL": "APPROVED",
                "MOCK_REVIEW_SECOND": "",
                "MOCK_REVIEW_USER": "reviewer",
                "MOCK_REVIEW_COMMIT": "",
                "MOCK_REVIEW_DISMISSED": "0",
                "MOCK_PR_EXISTS": "1",
                "MOCK_GITHUB_BARE": str(self.github),
            }
        )
        self._write_mock_gh()
        self._write_mock_curl()
        self._write_mock_ssh_keyscan()
        self._create_repository()
        self._write_mock_git()
        self._write_config()
        self._refresh_context_env()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str, cwd: Path | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd or self.work,
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _create_repository(self) -> None:
        subprocess.run(["git", "init", "--bare", str(self.github)], check=True, capture_output=True)
        self.work.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Fpr Test")
        self.git("config", "user.email", "fpr@example.test")
        (self.work / "file.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "file.txt")
        self.git("commit", "-m", "base")
        self.git("remote", "add", "origin", str(self.github))
        self.git("push", "origin", "main")
        self.git("remote", "set-url", "origin", "https://github.com/acme/project.git")
        self.git("switch", "-c", "feature/review")
        (self.work / "file.txt").write_text("base\nfeature\n", encoding="utf-8")
        self.git("add", "file.txt")
        self.git("commit", "-m", "add reviewed feature")

    def _write_config(self) -> None:
        key = self.root / "agent-key"
        token = self.root / "token"
        self.known_hosts = self.root / "forgejo-known-hosts"
        key.write_text("test private key\n", encoding="utf-8")
        token.write_text("supersecrettoken\n", encoding="utf-8")
        self.known_hosts.write_text(
            f"[127.0.0.1]:2222 ssh-ed25519 {self.host_key}\n",
            encoding="utf-8",
        )
        os.chmod(key, 0o600)
        os.chmod(token, 0o600)
        os.chmod(self.known_hosts, 0o600)
        config = Path(self.env["FPR_CONFIG_FILE"])
        config.write_text(
            textwrap.dedent(
                f"""\
                forgejo_url=http://127.0.0.1:3000
                forgejo_owner=fpr-agent
                forgejo_reviewer=reviewer
                forgejo_ssh_url=ssh://git@127.0.0.1:2222
                forgejo_ssh_key={key}
                forgejo_known_hosts_file={self.known_hosts}
                token_file={token}
                github_remote=origin
                """
            ),
            encoding="utf-8",
        )
        config.chmod(0o600)

    def _hash(self, value: str) -> str:
        return subprocess.run(
            ["git", "hash-object", "--stdin"],
            cwd=self.work,
            env=self.env,
            input=value,
            capture_output=True,
            check=True,
            text=True,
        ).stdout[:10]

    def _refresh_context_env(self) -> None:
        head = self.git("rev-parse", "HEAD")
        base = self.git("rev-parse", "main")
        repo_name = f"gh-acme-project-{self._hash('acme/project')}"
        suffix = f"{self._hash('feature/review')}-{self._hash('main')}-{base[:12]}"
        local_base = f"fpr/base/{suffix}"
        local_head = f"fpr/head/{suffix}"
        self.env.update(
            {
                "MOCK_HEAD": head,
                "MOCK_BASE": base,
                "MOCK_REPO_NAME": repo_name,
                "MOCK_LOCAL_BASE": local_base,
                "MOCK_LOCAL_HEAD": local_head,
            }
        )
        forgejo_bare = self.forgejo_root / f"{repo_name}.git"
        if not forgejo_bare.exists():
            subprocess.run(["git", "init", "--bare", str(forgejo_bare)], check=True, capture_output=True)

    def _write_mock_ssh_keyscan(self) -> None:
        path = self.bin / "ssh-keyscan"
        path.write_text(
            textwrap.dedent(
                f"""\
                #!/bin/sh
                printf '%s\\n' '[127.0.0.1]:2222 ssh-ed25519 {self.host_key}'
                """
            ),
            encoding="utf-8",
        )
        path.chmod(0o755)

    def _write_mock_git(self) -> None:
        path = self.bin / "git"
        path.write_text(
            textwrap.dedent(
                r"""
                #!/usr/bin/env python3
                import json
                import os
                import sys
                from pathlib import Path

                args = sys.argv[1:]
                with Path(os.environ["MOCK_GIT_ENV_LOG"]).open("a", encoding="utf-8") as log:
                    log.write(os.environ.get("FPR_FORGEJO_TOKEN", "") + "\n")
                with Path(os.environ["MOCK_GIT_ARGS_LOG"]).open("a", encoding="utf-8") as log:
                    log.write(json.dumps(args) + "\n")
                if args == ["rev-parse", "--is-shallow-repository"] and os.environ["MOCK_FORCE_SHALLOW"] == "1":
                    print("true")
                    sys.exit(0)
                if args and args[0] in {"fetch", "ls-remote", "push"}:
                    rewritten = []
                    prefix = "ssh://git@127.0.0.1:2222/fpr-agent/"
                    for arg in args:
                        if arg == "origin":
                            rewritten.append(os.environ["MOCK_GITHUB_BARE"])
                        elif arg.startswith(prefix):
                            rewritten.append("file://" + str(Path(os.environ["MOCK_FORGEJO_ROOT"]) / arg.removeprefix(prefix)))
                        else:
                            rewritten.append(arg)
                    args = rewritten
                os.execv(os.environ["REAL_GIT"], [os.environ["REAL_GIT"], *args])
                """
            ).lstrip(),
            encoding="utf-8",
        )
        path.chmod(0o755)
        self.env["MOCK_FORGEJO_ROOT"] = str(self.forgejo_root)

    def _write_mock_gh(self) -> None:
        path = self.bin / "gh"
        path.write_text(
            textwrap.dedent(
                r"""#!/bin/sh
                set -eu
                command=$1
                subcommand=$2
                if [ "$command $subcommand" = "repo view" ]; then
                  printf '%s\n' '{"nameWithOwner":"acme/project","defaultBranchRef":{"name":"main"}}'
                  exit 0
                fi
                if [ "$command $subcommand" = "pr view" ]; then
                  if [ -f "$MOCK_STATE/github-pr" ]; then
                    printf '{"url":"https://github.com/acme/project/pull/7","baseRefName":"main","baseRefOid":"%s","headRefName":"feature/review","headRefOid":"%s","state":"OPEN","number":7,"title":"PR"}\n' "$MOCK_BASE" "$MOCK_HEAD"
                    exit 0
                  fi
                  exit 1
                fi
                if [ "$command $subcommand" = "pr create" ]; then
                  : > "$MOCK_STATE/github-pr"
                  if [ -n "${MOCK_MOVE_BASE_ON_PR_CREATE:-}" ]; then
                    "$REAL_GIT" --git-dir "$MOCK_GITHUB_BARE" update-ref refs/heads/main "$MOCK_MOVE_BASE_ON_PR_CREATE"
                  fi
                  printf '%s\n' 'https://github.com/acme/project/pull/7'
                  exit 0
                fi
                echo "unexpected gh call: $*" >&2
                exit 99
                """
            ),
            encoding="utf-8",
        )
        path.chmod(0o755)

    def _write_mock_curl(self) -> None:
        path = self.bin / "curl"
        path.write_text(
            textwrap.dedent(
                r"""
                #!/usr/bin/env python3
                import json
                import os
                import subprocess
                import sys
                from pathlib import Path

                args = sys.argv[1:]
                with Path(os.environ["MOCK_CURL_LOG"]).open("a", encoding="utf-8") as log:
                    log.write(json.dumps(args) + "\n")
                output = Path(args[args.index("--output") + 1])
                method = args[args.index("--request") + 1]
                url = args[-1]
                state = Path(os.environ["MOCK_STATE"])
                repo_name = os.environ["MOCK_REPO_NAME"]
                head = os.environ["MOCK_HEAD"]
                base = os.environ["MOCK_BASE"]
                local_base = os.environ["MOCK_LOCAL_BASE"]
                local_head = os.environ["MOCK_LOCAL_HEAD"]
                review_user = os.environ["MOCK_REVIEW_USER"]
                review_commit = os.environ["MOCK_REVIEW_COMMIT"] or head
                review_dismissed = os.environ["MOCK_REVIEW_DISMISSED"] == "1"
                page = int(url.split("page=")[1].split("&")[0]) if "page=" in url else 1
                status = 200
                body = {}

                if url.endswith("/api/v1/user"):
                    body = {"login": "fpr-agent"}
                elif "/api/v1/users/" in url:
                    body = {"login": "reviewer"}
                elif url.endswith("/api/v1/user/repos") and method == "POST":
                    (state / "repo").touch()
                    status = 201
                    body = {"name": repo_name}
                elif "/collaborators/" in url and method == "PUT":
                    status = 204
                    body = None
                elif url.endswith(f"/api/v1/repos/fpr-agent/{repo_name}"):
                    if os.environ["MOCK_REPO_EXISTS"] == "0" and not (state / "repo").exists():
                        status = 404
                        body = {"message": "not found"}
                    else:
                        body = {
                            "owner": {"login": "fpr-agent"},
                            "name": repo_name,
                            "private": True,
                            "mirror": False,
                        }
                elif "/pulls?state=open" in url:
                    if page > 1 or (os.environ["MOCK_PR_EXISTS"] == "0" and not (state / "pull").exists()):
                        body = []
                    else:
                        body = [{
                            "number": 1,
                            "html_url": "http://127.0.0.1:3000/fpr-agent/repo/pulls/1",
                            "base": {"ref": local_base},
                            "head": {"ref": local_head},
                        }]
                elif url.endswith("/pulls") and method == "POST":
                    (state / "pull").touch()
                    status = 201
                    body = {"number": 1, "html_url": "http://127.0.0.1:3000/fpr-agent/repo/pulls/1"}
                elif url.endswith("/pulls/1"):
                    body = {
                        "number": 1,
                        "html_url": "http://127.0.0.1:3000/fpr-agent/repo/pulls/1",
                        "state": "open",
                        "base": {"ref": local_base, "sha": base},
                        "head": {"ref": local_head, "sha": head},
                    }
                elif "/pulls/1/reviews?" in url:
                    approval = os.environ["MOCK_APPROVAL"]
                    second = os.environ["MOCK_REVIEW_SECOND"]
                    if page == 1 and approval != "NONE":
                        body = [{
                            "id": 9,
                            "state": "APPROVED",
                            "commit_id": review_commit,
                            "stale": approval == "STALE",
                            "dismissed": review_dismissed,
                            "user": {"login": review_user},
                        }]
                    elif page == 2 and second:
                        body = [{
                            "id": 10,
                            "state": second,
                            "commit_id": review_commit,
                            "stale": False,
                            "dismissed": review_dismissed,
                            "user": {"login": review_user},
                        }]
                    else:
                        body = []
                    move_to = os.environ.get("MOCK_MOVE_BASE_TO", "")
                    if move_to and page == 1:
                        subprocess.run(
                            ["git", "--git-dir", os.environ["MOCK_GITHUB_BARE"], "update-ref", "refs/heads/main", move_to],
                            check=True,
                        )
                elif url.endswith("/pulls/1") and method == "PATCH":
                    body = {"number": 1}
                else:
                    status = 500
                    body = {"message": f"unexpected curl request: {method} {url}"}

                output.write_text("" if body is None else json.dumps(body), encoding="utf-8")
                sys.stdout.write(str(status))
                """
            ).lstrip(),
            encoding="utf-8",
        )
        path.chmod(0o755)

    def run_fpr(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["/bin/sh", str(SCRIPT), *args],
            cwd=self.work,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def remote_ref(self, ref: str) -> str:
        result = subprocess.run(
            ["git", "--git-dir", str(self.github), "rev-parse", "--verify", ref],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def test_status_accepts_only_an_exact_non_stale_approval(self) -> None:
        result = self.run_fpr("status")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ready:       yes", result.stdout)
        self.assertIn(self.env["MOCK_HEAD"], result.stdout)
        self.assertNotIn("supersecrettoken", self.curl_log.read_text())

    def test_status_rejects_a_stale_approval(self) -> None:
        self.env["MOCK_APPROVAL"] = "STALE"

        result = self.run_fpr("status")

        self.assertEqual(result.returncode, 1)
        self.assertIn("Review:      NONE", result.stdout)
        self.assertIn("Ready:       no", result.stdout)

    def test_status_uses_later_review_pages(self) -> None:
        self.env["MOCK_REVIEW_SECOND"] = "REQUEST_CHANGES"

        result = self.run_fpr("status")

        self.assertEqual(result.returncode, 1)
        self.assertIn("Review:      REQUEST_CHANGES", result.stdout)
        calls = [json.loads(line) for line in self.curl_log.read_text().splitlines()]
        self.assertTrue(any("page=3" in call[-1] for call in calls))

    def test_status_rejects_wrong_reviewer_commit_and_dismissed_review(self) -> None:
        cases = (
            ("MOCK_REVIEW_USER", "someone-else"),
            ("MOCK_REVIEW_COMMIT", "0" * 40),
            ("MOCK_REVIEW_DISMISSED", "1"),
        )
        for key, value in cases:
            with self.subTest(key=key):
                original = self.env[key]
                self.env[key] = value
                result = self.run_fpr("status")
                self.env[key] = original
                self.assertEqual(result.returncode, 1)
                self.assertIn("Ready:       no", result.stdout)

    def test_same_sha_on_a_different_base_name_requires_a_new_pr(self) -> None:
        subprocess.run(
            [self.real_git, "--git-dir", str(self.github), "update-ref", "refs/heads/release", self.env["MOCK_BASE"]],
            check=True,
        )

        result = self.run_fpr("status", "--base", "release")

        self.assertEqual(result.returncode, 1)
        self.assertIn("not open for this base generation", result.stdout)

    def test_open_creates_repository_pushes_review_refs_and_creates_pr(self) -> None:
        self.env["MOCK_REPO_EXISTS"] = "0"
        self.env["MOCK_PR_EXISTS"] = "0"

        result = self.run_fpr("open", "--no-browser")

        self.assertEqual(result.returncode, 0, result.stderr)
        local_bare = self.forgejo_root / f"{self.env['MOCK_REPO_NAME']}.git"
        base = subprocess.run(
            ["git", "--git-dir", str(local_bare), "rev-parse", f"refs/heads/{self.env['MOCK_LOCAL_BASE']}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        head = subprocess.run(
            ["git", "--git-dir", str(local_bare), "rev-parse", f"refs/heads/{self.env['MOCK_LOCAL_HEAD']}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(base, self.env["MOCK_BASE"])
        self.assertEqual(head, self.env["MOCK_HEAD"])
        self.assertTrue((self.state / "pull").exists())

    def test_open_pushes_shallow_base_and_head_sequentially(self) -> None:
        self.env["MOCK_FORCE_SHALLOW"] = "1"
        self.env["MOCK_PR_EXISTS"] = "0"

        result = self.run_fpr("open", "--no-browser")

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in self.git_args_log.read_text().splitlines()]
        forgejo_pushes = [
            call
            for call in calls
            if call[:1] == ["push"]
            and any(arg.startswith("ssh://git@127.0.0.1:2222/") for arg in call)
        ]
        self.assertEqual(len(forgejo_pushes), 2)
        self.assertTrue(all("--atomic" not in call for call in forgejo_pushes))
        self.assertTrue(any(self.env["MOCK_LOCAL_BASE"] in arg for arg in forgejo_pushes[0]))
        self.assertTrue(any(self.env["MOCK_LOCAL_HEAD"] in arg for arg in forgejo_pushes[1]))

    def test_ship_rejects_without_approval_and_does_not_push(self) -> None:
        self.env["MOCK_APPROVAL"] = "NONE"

        result = self.run_fpr("ship", "--no-browser")

        self.assertEqual(result.returncode, 2)
        self.assertIn("not approved for shipping", result.stderr)
        self.assertEqual(self.remote_ref("refs/heads/feature/review"), "")
        self.assertFalse((self.state / "github-pr").exists())

    def test_ship_pushes_exact_approved_sha_and_creates_github_pr(self) -> None:
        result = self.run_fpr("ship", "--no-browser")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.remote_ref("refs/heads/feature/review"), self.env["MOCK_HEAD"])
        self.assertTrue((self.state / "github-pr").exists())
        self.assertIn(f"Published approved SHA: {self.env['MOCK_HEAD']}", result.stdout)

    def test_ship_rejects_if_github_base_moves_after_review_check(self) -> None:
        self.git("switch", "main")
        (self.work / "base-2.txt").write_text("new base\n", encoding="utf-8")
        self.git("add", "base-2.txt")
        self.git("commit", "-m", "advance base")
        moved_base = self.git("rev-parse", "HEAD")
        self.git("push", str(self.github), f"{moved_base}:refs/fpr-test/moved-base")
        self.git("switch", "feature/review")
        self.env["MOCK_MOVE_BASE_TO"] = moved_base

        result = self.run_fpr("ship", "--no-browser")

        self.assertEqual(result.returncode, 2)
        self.assertIn("GitHub base moved", result.stderr)
        self.assertEqual(self.remote_ref("refs/heads/feature/review"), "")

    def test_ship_rejects_divergent_existing_github_branch(self) -> None:
        tree = subprocess.run(
            [self.real_git, "mktree"],
            cwd=self.work,
            env=self.env,
            input="",
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
        unrelated = subprocess.run(
            [self.real_git, "commit-tree", tree],
            cwd=self.work,
            env=self.env,
            input="unrelated\n",
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
        self.git("push", str(self.github), f"{unrelated}:refs/heads/feature/review")

        result = self.run_fpr("ship", "--no-browser")

        self.assertEqual(result.returncode, 2)
        self.assertIn("refusing to force-push", result.stderr)
        self.assertEqual(self.remote_ref("refs/heads/feature/review"), unrelated)

    def test_ship_rejects_multiple_push_urls_before_api_or_push(self) -> None:
        self.git("config", "--add", "remote.origin.pushurl", "https://github.com/acme/project.git")
        self.git("config", "--add", "remote.origin.pushurl", "https://github.com/acme/other.git")

        result = self.run_fpr("ship", "--no-browser")

        self.assertEqual(result.returncode, 2)
        self.assertIn("exactly one push URL", result.stderr)
        self.assertFalse(self.curl_log.exists())

    def test_ship_detects_base_move_during_github_pr_creation(self) -> None:
        self.git("switch", "main")
        (self.work / "base-race.txt").write_text("race\n", encoding="utf-8")
        self.git("add", "base-race.txt")
        self.git("commit", "-m", "race base")
        moved_base = self.git("rev-parse", "HEAD")
        self.git("push", str(self.github), f"{moved_base}:refs/fpr-test/race-base")
        self.git("switch", "feature/review")
        self.env["MOCK_MOVE_BASE_ON_PR_CREATE"] = moved_base

        result = self.run_fpr("ship", "--no-browser")

        self.assertEqual(result.returncode, 2)
        self.assertIn("GitHub base moved", result.stderr)

    def test_rejects_forgejo_url_with_userinfo_authority_bypass(self) -> None:
        config = Path(self.env["FPR_CONFIG_FILE"])
        config.write_text(
            config.read_text().replace(
                "http://127.0.0.1:3000",
                "http://localhost:3000@attacker.example",
            ),
            encoding="utf-8",
        )

        result = self.run_fpr("doctor")

        self.assertEqual(result.returncode, 2)
        self.assertIn("loopback host and port", result.stderr)
        self.assertFalse(self.curl_log.exists())

    def test_rejects_a_changed_forgejo_host_key_before_sending_the_token(self) -> None:
        self.known_hosts.write_text(
            "[127.0.0.1]:2222 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPuAfakeChangedHostKey000000000000000000\n",
            encoding="utf-8",
        )

        result = self.run_fpr("doctor")

        self.assertEqual(result.returncode, 2)
        self.assertIn("host key changed", result.stderr)
        self.assertFalse(self.curl_log.exists())

    def test_rejects_a_permissive_known_hosts_file(self) -> None:
        self.known_hosts.chmod(0o644)

        result = self.run_fpr("doctor")

        self.assertEqual(result.returncode, 2)
        self.assertIn("must have mode 0400 or 0600", result.stderr)
        self.assertFalse(self.curl_log.exists())

    def test_token_override_is_removed_from_subprocess_environment(self) -> None:
        self.env["FPR_FORGEJO_TOKEN"] = "overrideSecret"

        result = self.run_fpr("status")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("overrideSecret", self.git_env_log.read_text())
        self.assertNotIn("overrideSecret", self.curl_log.read_text())
        calls = [json.loads(line) for line in self.curl_log.read_text().splitlines()]
        self.assertTrue(all("--disable" in call and "--noproxy" in call for call in calls))

    def test_rejects_running_from_github_default_branch_with_an_override(self) -> None:
        self.git("switch", "main")
        self.git("push", str(self.github), "main:refs/heads/release")

        result = self.run_fpr("ship", "--base", "release", "--no-browser")

        self.assertEqual(result.returncode, 2)
        self.assertIn("refusing to operate from the GitHub default branch", result.stderr)
        self.assertFalse(self.curl_log.exists())

    def test_losing_a_lock_race_does_not_remove_the_other_process_lock(self) -> None:
        repo_root = self.git("rev-parse", "--show-toplevel")
        lock = Path(self.env.get("TMPDIR", "/tmp")) / f"fpr-{self._hash(repo_root)}.lock"
        lock.mkdir()
        try:
            result = self.run_fpr("status")

            self.assertEqual(result.returncode, 2)
            self.assertIn("another fpr command is already running", result.stderr)
            self.assertTrue(lock.is_dir())
        finally:
            lock.rmdir()

    def test_ship_rejects_dirty_worktree_before_api_or_push(self) -> None:
        (self.work / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")

        result = self.run_fpr("ship", "--no-browser")

        self.assertEqual(result.returncode, 2)
        self.assertIn("worktree must be clean", result.stderr)
        self.assertEqual(self.remote_ref("refs/heads/feature/review"), "")
        self.assertFalse(self.curl_log.exists())


if __name__ == "__main__":
    unittest.main()
