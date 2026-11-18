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


def patch(path, *lines):
    """A patch that adds `lines` to `path`."""
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +1 @@\n" + "".join(f"+{l}\n" for l in lines)


# Each commit is files in $MOCK_COMMITS, listed in $MOCK_SHAS: <id>.msg, <id>.diff, and the NUL-separated names Git
# lists with --diff-filter=ACMRT (<id>.names) and without it (<id>.allnames).
GIT = r"""
for last; do :; done
case "$*" in
  "rev-parse --show-toplevel") echo "$MOCK_ROOT" ;;
  "rev-parse --path-format=absolute --git-common-dir") echo "$MOCK_ROOT/.git" ;;
  "remote get-url origin") echo "$MOCK_ORIGIN" ;;
  "rev-list --reverse $last") for sha in $MOCK_SHAS; do echo "$sha"; done ;;
  "show -s --format=%B $last") cat "$MOCK_COMMITS/$last.msg" ;;
  "show --format= -M --no-relative --diff-merges=first-parent --name-only -z --diff-filter=ACMRT $last")
    cat "$MOCK_COMMITS/$last.names" 2>/dev/null || true ;;
  "show --format= -M --no-relative --diff-merges=first-parent --name-only -z $last")
    cat "$MOCK_COMMITS/$last.allnames" 2>/dev/null || cat "$MOCK_COMMITS/$last.names" 2>/dev/null || true ;;
  "show --format= -M --no-relative --diff-merges=first-parent --patch --text --no-color --no-ext-diff $last")
    cat "$MOCK_COMMITS/$last.diff" ;;
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

    def commit(self, sha, message, diff, names=("a.md",), deleted=()):
        (self.commits / f"{sha}.msg").write_text(message)
        (self.commits / f"{sha}.diff").write_text(diff)
        (self.commits / f"{sha}.names").write_text("".join(f"{n}\0" for n in names))
        (self.commits / f"{sha}.allnames").write_text("".join(f"{n}\0" for n in (*names, *deleted)))
        self.env["MOCK_SHAS"] += f" {sha}"

    def check(self, *args, range_="main..topic"):
        return subprocess.run([sys.executable, str(SCRIPT), range_, *args], env=self.env,
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
        self.commit("c1", "feat: add\n", patch("a.md", f"see {notes}x"))
        self.commit("c2", "fix: drop\n", f"--- a/a.md\n+++ b/a.md\n@@ -1 +1 @@\n-see {notes}x\n+see the notes\n")
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
        self.commit("c1", "feat: zebra\n", patch("a.md", "notes for project zebra"))
        result = self.check("--branch", "kaizen/alice-mbp-fix")
        self.assert_hit(result, "commit c1 diff: private term 'Project Zebra'",
                        "--branch: a host.toml value ('alice-mbp')")
        self.assertNotIn("comment", result.stderr)

    def test_owner_login_passes_but_home_directory_fails(self):
        self.commit("c1", "docs: link\n\nSee https://github.com/alice/dotfiles/pull/1.\n",
                    patch("a.md", "Merge pull request #1 from alice/kaizen/x"))
        result = self.check()
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        body = self.root / "body.md"
        body.write_text(f"Checked out at {local('Users', 'alice')[:-1]} on this Mac.\n")
        result = self.check("--body-file", str(body))
        self.assert_hit(result, "--body-file: a host.toml value (")
        self.assertNotIn("'alice'", result.stderr)

    def test_login_is_matched_in_other_host_fields(self):
        (self.checkout / "host.toml").write_text('username = "alice"\nhostName = "alice"\n')
        self.commit("c1", "docs: link\n\nSee https://github.com/alice/dotfiles.\n", CLEAN_DIFF)
        self.assert_hit(self.check(), "commit c1 message: a host.toml value ('alice')")

    def test_only_destination_paths_and_added_lines(self):
        (self.home / ".claude/kaizen/private-terms").write_text("秘密\n")
        new = "メモ/秘密.md"
        quoted = "".join(c if c.isascii() else "".join(f"\\{b:03o}" for b in c.encode()) for c in new)
        diff = ("diff --git a/alice-mbp.md b/notes.md\nsimilarity index 90%\nrename from alice-mbp.md\n"
                "rename to notes.md\n--- a/alice-mbp.md\n+++ b/notes.md\n@@ -1 +1 @@\n-x\n+y\n"
                "diff --git a/alice-mbp-old.md b/alice-mbp-old.md\ndeleted file mode 100644\n"
                "--- a/alice-mbp-old.md\n+++ /dev/null\n@@ -1 +0,0 @@\n-gone\n"
                f'diff --git "a/{quoted}" "b/{quoted}"\nnew file mode 100644\n--- /dev/null\n+++ "b/{quoted}"\n'
                "@@ -0,0 +1 @@\n+hello\n")
        self.commit("c1", "docs: move notes\n", diff, names=("notes.md", new), deleted=("alice-mbp-old.md",))
        result = self.check()
        self.assert_hit(result, "commit c1 path: private term '秘密'")
        self.assertNotIn("alice-mbp", result.stderr)

    def test_volume_and_bare_home_paths(self):
        self.commit("c1", f"fix: paths\n\nCopied from {local('Volumes', 'Data')}x and cd {local('Users', 'erin')[:-1]}\n",
                    CLEAN_DIFF)
        self.assert_hit(self.check(), f"local path '{local('Volumes', 'Data')}'",
                        f"local path '{local('Users', 'erin')[:-1]}'")

    def test_only_two_dot_ranges(self):
        for range_ in ("topic", "main...topic", "..topic", "main.."):
            with self.subTest(range_=range_):
                result = self.check(range_=range_)
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_undecodable_input_is_an_error(self):
        body = self.root / "body.md"
        body.write_bytes(b"\xff\xfe broken\n")
        for args in (("--body-file", str(body)), ()):
            with self.subTest(args=args):
                result = self.check(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("cannot read", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                (self.home / ".claude/kaizen/private-terms").write_bytes(b"\xff\n")


if __name__ == "__main__":
    unittest.main()
