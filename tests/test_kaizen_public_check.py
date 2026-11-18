from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/kaizen/public-check"


def local(*parts):
    """An absolute path built at run time, so this file publishes no literal local path: local("Users", "a")."""
    return "/" + "/".join(parts) + "/"


# Each commit is a pair of files in $MOCK_COMMITS: <id>.msg and <id>.diff, listed in $MOCK_SHAS.
GIT = r"""
case "$*" in
  "rev-parse --show-toplevel") echo "$MOCK_ROOT" ;;
  "rev-parse --path-format=absolute --git-common-dir") echo "$MOCK_ROOT/.git" ;;
  "remote get-url origin") echo "$MOCK_ORIGIN" ;;
  "rev-list --reverse main..topic") for sha in $MOCK_SHAS; do echo "$sha"; done ;;
  "show -s --format=%B "*) cat "$MOCK_COMMITS/$4.msg" ;;
  "show --format= --patch --text --no-color --no-ext-diff --diff-merges=first-parent "*) cat "$MOCK_COMMITS/$8.diff" ;;
  *) echo "unexpected: git $*" >&2; exit 1 ;;
esac
"""

CLEAN_DIFF = f"""diff --git a/home/dot_claude/CLAUDE.md b/home/dot_claude/CLAUDE.md
--- a/home/dot_claude/CLAUDE.md
+++ b/home/dot_claude/CLAUDE.md
@@ -1,3 +1,3 @@ see {local("Users", "context")}heading
 context line mentioning {local("Users", "carol", "old")}
-removed line with {local("home", "dave", "old")}
+Build for aarch64-darwin on the personal role, under ~/.claude/.
"""


class PublicCheckTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        cat = shutil.which("cat")
        self.assertIsNotNone(cat)
        (self.bin / "cat").symlink_to(cat)
        git = self.bin / "git"
        git.write_text("#!/bin/sh\n" + GIT)
        git.chmod(0o755)
        self.checkout = self.root / "checkout"
        (self.checkout / "nix").mkdir(parents=True)
        (self.checkout / "host.toml").write_text(
            f'system = "aarch64-darwin"\nusername = "alice"\nhomeDirectory = "{local("Users", "alice")[:-1]}"\n'
            'hostName = "alice-mbp"\nrole = "personal"\n')
        (self.checkout / "nix/host.default.toml").write_text('system = "aarch64-darwin"\nusername = "user"\n')
        (self.checkout / "nix/roles.toml").write_text("[minimal]\n[personal]\n")
        self.commits = self.root / "commits"
        self.commits.mkdir()
        self.home = self.root / "home"
        (self.home / ".claude/kaizen").mkdir(parents=True)
        self.env = {
            "PATH": str(self.bin),
            "HOME": str(self.home),
            "MOCK_ROOT": str(self.checkout),
            "MOCK_COMMITS": str(self.commits),
            "MOCK_SHAS": "",
            "MOCK_ORIGIN": "git@github.com:Alice/dotfiles.git",
        }

    def commit(self, sha, message, diff):
        (self.commits / f"{sha}.msg").write_text(message)
        (self.commits / f"{sha}.diff").write_text(diff)
        self.env["MOCK_SHAS"] += f" {sha}"

    def check(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "main..topic", *args], env=self.env,
                              cwd=self.checkout, capture_output=True, text=True, timeout=10)

    def assert_hit(self, result, *needles):
        self.assertEqual(result.returncode, 1, result.stderr)
        for needle in needles:
            self.assertIn(needle, result.stderr)

    def test_clean_range_and_metadata_pass(self):
        self.commit("c1", "docs: describe the role\n", CLEAN_DIFF)
        self.commit("c2", "fix: tidy\n", CLEAN_DIFF)
        body = self.root / "body.md"
        body.write_text("Edits home/dot_claude/CLAUDE.md for aarch64-darwin.\n")
        result = self.check("--title", "docs: role", "--body-file", str(body), "--branch", "kaizen/role")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_local_path_in_an_intermediate_commit(self):
        notes = local("Users", "erin", "notes")
        self.commit("c1", "feat: add\n", f"+++ b/a.md\n+see {notes}x\n")
        self.commit("c2", "fix: drop\n", f"--- a/a.md\n+++ b/a.md\n-see {notes}x\n+see the notes\n")
        result = self.check()
        self.assert_hit(result, f"commit c1 diff: local path '{local('Users', 'erin')}'")
        self.assertNotIn("c2", result.stderr)

    def test_local_path_only_in_a_commit_message(self):
        self.commit("c1", f"fix: path\n\nFound under {local('home', 'bob', 'work')}.\n", CLEAN_DIFF)
        self.assert_hit(self.check(), f"commit c1 message: local path '{local('home', 'bob')}'")

    def test_local_path_only_in_the_pr_body(self):
        self.commit("c1", "docs: note\n", CLEAN_DIFF)
        body = self.root / "body.md"
        body.write_text(f"Ran in {local('private', 'var', 'folders', 'xy', 'T')}.\n")
        self.assert_hit(self.check("--body-file", str(body)),
                        f"--body-file: local path '{local('private', 'var', 'folders')}'")

    def test_private_term_and_host_value(self):
        (self.home / ".claude/kaizen/private-terms").write_text("# comment\nProject Zebra\n")
        self.commit("c1", "feat: zebra\n", "+++ b/a.md\n+notes for project zebra\n")
        result = self.check("--branch", "kaizen/alice-mbp-fix")
        self.assert_hit(result, "commit c1 diff: private term 'Project Zebra'",
                        "--branch: a host.toml value ('alice-mbp')")
        self.assertNotIn("comment", result.stderr)

    def test_owner_login_passes_but_home_directory_fails(self):
        self.commit("c1", "docs: link\n\nSee https://github.com/alice/dotfiles/pull/1.\n",
                    "+++ b/a.md\n+Merge pull request #1 from alice/kaizen/x\n")
        result = self.check()
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        body = self.root / "body.md"
        body.write_text(f"Checked out at {local('Users', 'alice')[:-1]} on this Mac.\n")
        result = self.check("--body-file", str(body))
        self.assert_hit(result, "--body-file: a host.toml value (")
        self.assertNotIn("'alice'", result.stderr)


if __name__ == "__main__":
    unittest.main()
