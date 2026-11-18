from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/dot_claude/bin/executable_merge-pr"
HEAD = "a" * 40
MANAGED = (REPO / ".claude/kaizen-managed").read_text()

GH = r"""
echo "gh $*" >> "$MOCK_LOG"
case "$*" in
  "pr view 7 --json headRefOid,"*)
    printf '{"headRefOid":"%s","baseRefName":"main","state":"OPEN","isDraft":false,"mergeable":"MERGEABLE"}\n' "$MOCK_HEAD" ;;
  "repo view --json"*)
    echo '{"nameWithOwner":"o/r","mergeCommitAllowed":true,"squashMergeAllowed":false,"rebaseMergeAllowed":false}' ;;
  "pr view 7 --json commits"*) echo "feat: change" ;;
  "pr checks 7 --json name,bucket") echo '[{"name":"ci","bucket":"pass"}]' ;;
  "api graphql"*) echo false ;;
  "pr merge 7 --merge --match-head-commit $MOCK_HEAD") touch "$MOCK_MERGED" ;;
  "pr view 7 --json state,headRefOid,mergeCommit"*)
    if [ -e "$MOCK_MERGED" ]; then echo "MERGED $MOCK_HEAD 123456789"; else echo "OPEN $MOCK_HEAD "; fi ;;
  *) echo "unexpected: gh $*" >&2; exit 1 ;;
esac
"""

# Only origin/main holds the list; any other revision (the PR head) reads as empty, so a script that read the head
# instead of the base would let the PR through.
GIT = r"""
echo "git $*" >> "$MOCK_LOG"
case "$*" in
  "rev-parse --show-toplevel") echo "$MOCK_ROOT" ;;
  "-C . rev-parse --path-format=absolute --git-common-dir") echo "$MOCK_ROOT/.git" ;;
  "-C $MOCK_SOURCE rev-parse --path-format=absolute --git-common-dir") echo "$MOCK_SOURCE_COMMON" ;;
  "fetch -q --no-tags origin +refs/heads/main:refs/remotes/origin/main") ;;
  "show refs/remotes/origin/main:.claude/kaizen-managed")
    if [ -f "$MOCK_BASE_LIST" ]; then cat "$MOCK_BASE_LIST"; else echo "fatal: path does not exist" >&2; exit 128; fi ;;
  "show "*) ;;
  "cat-file -e $MOCK_HEAD^{commit}") ;;
  "merge-base refs/remotes/origin/main $MOCK_HEAD") echo base0 ;;
  "diff --name-only --no-renames -z base0 $MOCK_HEAD") printf '%s\n' "$MOCK_CHANGED" | tr '\n' '\0' ;;
  *) echo "unexpected: git $*" >&2; exit 1 ;;
esac
"""


class MergePrManagedPathTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        # Keep PATH to this directory so only the stubs and these tools are reachable.
        for command in ("jq", "mktemp", "rm", "grep", "cat", "tr", "touch", "sleep"):
            path = shutil.which(command)
            self.assertIsNotNone(path, f"{command} is required")
            (self.bin / command).symlink_to(path)
        self.checkout = self.root / "checkout"
        (self.checkout / ".claude").mkdir(parents=True)
        self.base_list = self.root / "base-list"
        self.base_list.write_text(MANAGED)
        self.env = {
            "PATH": str(self.bin),
            "HOME": str(self.root),
            "MOCK_LOG": str(self.root / "log"),
            "MOCK_HEAD": HEAD,
            "MOCK_ROOT": str(self.checkout),
            "MOCK_SOURCE": str(self.root / "source/home"),
            "MOCK_SOURCE_COMMON": str(self.root / "source/.git"),
            "MOCK_BASE_LIST": str(self.base_list),
            "MOCK_MERGED": str(self.root / "merged"),
            "MOCK_CHANGED": "README.md",
        }
        self.mock("gh", GH)
        self.mock("git", GIT)
        self.mock("chezmoi", 'echo "$MOCK_SOURCE"')

    def mock(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def in_dotfiles(self):
        self.env["MOCK_SOURCE_COMMON"] = str(self.checkout / ".git")

    def run_merge(self, *changed):
        self.env["MOCK_CHANGED"] = "\n".join(changed)
        return subprocess.run([shutil.which("bash"), str(SCRIPT), "7", HEAD[:12]], env=self.env,
                              cwd=self.checkout, capture_output=True, text=True, timeout=10)

    def merged(self):
        return (self.root / "merged").exists()

    def assert_owner_only(self, result, path):
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("only the owner merges it", result.stderr)
        self.assertIn("enabling auto-merge on the checked head", result.stderr)
        self.assertIn(path, result.stderr.splitlines())
        self.assertFalse(self.merged())

    def test_refuses_each_kind_of_managed_path(self):
        for path in ("home/dot_claude/skills/hiden/SKILL.md", "home/dot_claude/bin/executable_merge-pr",
                     "home/.chezmoiignore", "home/.chezmoiremove", "home/.chezmoitemplates/agents/AGENTS.md",
                     "scripts/kaizen/public-check", "docs/kaizen.md"):
            with self.subTest(path=path):
                self.assert_owner_only(self.run_merge("README.md", path), path)

    def test_refuses_a_pr_that_edits_the_list(self):
        self.assert_owner_only(self.run_merge(".claude/kaizen-managed"), ".claude/kaizen-managed")

    def test_base_list_applies_when_the_head_deletes_or_empties_it(self):
        head_list = self.checkout / ".claude/kaizen-managed"
        for head_state in ("deleted", "emptied"):
            with self.subTest(head=head_state):
                if head_state == "emptied":
                    head_list.write_text("")
                self.assert_owner_only(self.run_merge(".claude/kaizen-managed", "home/dot_claude/CLAUDE.md"),
                                       "home/dot_claude/CLAUDE.md")

    def test_dotfiles_refuses_when_the_base_has_no_list(self):
        self.in_dotfiles()
        self.base_list.unlink()
        result = self.run_merge("README.md")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not read .claude/kaizen-managed from origin/main", result.stderr)
        self.assertFalse(self.merged())

    def test_unmanaged_paths_merge(self):
        self.in_dotfiles()
        result = self.run_merge("README.md", "home/dot_config/git/config", "scripts/chezmoi-plan.sh",
                                "docs/kaizen-notes.md", "home/.chezmoiexternal.toml")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"MERGED {HEAD} 123456789\n")
        self.assertTrue(self.merged())

    def test_other_repository_without_a_list_merges(self):
        self.base_list.unlink()
        result = self.run_merge("home/dot_claude/CLAUDE.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.merged())


if __name__ == "__main__":
    unittest.main()
