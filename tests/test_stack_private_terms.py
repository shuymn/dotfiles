from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock
import importlib.machinery
import importlib.util
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/stack-private-terms"
# The last main commit whose generator read host.toml through a helper script retired since; its scripts/ tree
# is the parity baseline.
LEGACY = "e53e5351c84dd8aaf93dca88d04528edf84d0904"
OWNER = "octo-owner"
HOME_DIR = "/" + "Users/" + OWNER  # split so the committed line is not a local path itself
HOST_TOML = (
    'system = "aarch64-darwin"\n'  # generic: in nix/host.default.toml
    f'username = "{OWNER}"\n'  # the owner in origin's URL
    f'homeDirectory = "{HOME_DIR}"\n'
    'hostName = "example-host"\n'
    'computerName = "Example Mac"\n'
    'role = "personal"\n'  # a role name in nix/roles.toml
    'blank = "  "\n'
    'count = 3\n'
    '[displays]\nmain = "Example Display"\n'  # a table, not a string value
)
WORKTREE_HOST_TOML = 'hostName = "worktree-host"\n'  # the linked worktree's own host.toml
HAND_KEPT = "# a comment\n  project-codename  \n\nexample-client\n"
EXPECTED = {HOME_DIR, "example-host", "Example Mac", "worktree-host", "project-codename", "example-client",
            *(f".t3/{name}/" for name in ("scratch", "worktrees", "userdata"))}  # built so no line is a local path


def git(cwd, *args, env=None):
    return subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com",
                           "-c", "commit.gpgsign=false", *args], cwd=cwd, env=env, check=True,
                          capture_output=True, text=True).stdout


class StackPrivateTermsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="stack-private-terms-test-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))

    def checkout(self, name, scripts):
        """A linked worktree of a repository holding the generic nix files and the given scripts at HEAD; the main
        checkout and the worktree each have a host.toml with a value the other lacks."""
        root = self.tmp / name
        (root / "nix").mkdir(parents=True)
        (root / "nix/host.default.toml").write_text(
            'system = "aarch64-darwin"\nusername = "user"\nhostName = "localhost"\ncomputerName = "Mac"\n'
            'role = "minimal"\n')
        (root / "nix/roles.toml").write_text('[minimal]\ndarwin = []\n\n[personal]\ndarwin = ["dev"]\n')
        for rel, text in scripts.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text)
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.tmp), "GIT_CONFIG_NOSYSTEM": "1"}
        git(root, "init", "-q", env=env)
        git(root, "remote", "add", "origin", f"https://github.com/{OWNER}/dotfiles.git", env=env)
        git(root, "add", ".", env=env)
        git(root, "commit", "-q", "-m", "fixture", env=env)
        (root / "host.toml").write_text(HOST_TOML)
        worktree = self.tmp / f"{name}-worktree"
        git(root, "worktree", "add", "-q", str(worktree), env=env)
        (worktree / "host.toml").write_text(WORKTREE_HOST_TOML)
        return worktree

    def run_generator(self, root, terms_file):
        """Run root's generator with a fresh HOME holding the hand-kept list at terms_file; the written file."""
        home = self.tmp / f"home-{root.name}"
        (home / terms_file).parent.mkdir(parents=True)
        (home / terms_file).write_text(HAND_KEPT)
        p = subprocess.run([sys.executable, str(root / "scripts/stack-private-terms")], capture_output=True, text=True,
                           timeout=60, env={"PATH": os.environ.get("PATH", ""), "HOME": str(home),
                                            "GIT_CONFIG_NOSYSTEM": "1"})
        self.assertEqual(p.returncode, 0, p.stderr)
        return home / ".config/stack/private-terms"

    @staticmethod
    def terms(path):
        return {t for line in path.read_text().splitlines() if (t := line.strip()) and not t.startswith("#")}

    def generate(self):
        """The current generator, in a checkout holding no other script."""
        root = self.checkout("current", {"scripts/stack-private-terms": SCRIPT.read_text()})
        return self.run_generator(root, ".config/stack/private-terms.local")

    def test_writes_private_values_hand_kept_terms_and_t3_fragments(self):
        out = self.generate()
        self.assertEqual(self.terms(out), EXPECTED)
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
        self.assertTrue(out.read_text().startswith("# "))

    def test_term_set_equals_the_legacy_generator(self):
        p = subprocess.run(["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", LEGACY, "scripts"],
                           capture_output=True, text=True)
        if p.returncode != 0:
            self.skipTest("needs the legacy commit (CI checks out one commit)")
        legacy = {rel: git(REPO, "show", f"{LEGACY}:{rel}") for rel in p.stdout.splitlines()}
        old = self.run_generator(self.checkout("legacy", legacy), ".claude/kaizen/private-terms")
        new = self.generate()
        self.assertEqual(self.terms(new), self.terms(old))
        self.assertEqual(stat.S_IMODE(new.stat().st_mode), stat.S_IMODE(old.stat().st_mode))

    def test_a_host_file_that_vanishes_exits_2_and_keeps_the_output(self):
        root = self.checkout("vanish", {"scripts/stack-private-terms": SCRIPT.read_text()})
        (root / "host.toml").unlink()  # is_file below still selects it, as if it vanished after the check
        loader = importlib.machinery.SourceFileLoader("stack_private_terms", str(root / "scripts/stack-private-terms"))
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(module)
        module.TARGET = self.tmp / "out/private-terms"
        module.TARGET.parent.mkdir()
        module.TARGET.write_text("previous\n")
        with mock.patch.object(Path, "is_file", return_value=True), redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit) as raised:
            module.main()
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(module.TARGET.read_text(), "previous\n")


if __name__ == "__main__":
    unittest.main()
