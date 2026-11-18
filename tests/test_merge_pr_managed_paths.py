from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/dot_claude/bin/executable_merge-pr"
HEAD = "a" * 40
BASE = "b" * 40
MANAGED = (REPO / ".claude/kaizen-managed").read_text()

GH = r"""
echo "gh $*" >> "$MOCK_LOG"
case "$*" in
  "pr view 7 --json headRefOid,"*)
    printf '{"headRefOid":"%s","baseRefName":"main","state":"OPEN","isDraft":false,"mergeable":"MERGEABLE"}\n' "$MOCK_HEAD" ;;
  "pr view 7 --json baseRefName -q .baseRefName") echo "${MOCK_BASE_NOW:-main}" ;;
  "api repos/o/r/git/ref/heads/main -q .object.sha") echo "${MOCK_BASE_SHA_NOW:-$MOCK_BASE_SHA}" ;;
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

# Only the base commit holds the list, so a script that read the PR head or the working tree would let the PR through.
# A diff or log without --no-relative behaves as with diff.relative=true: from a subdirectory it lists only the paths
# below it, relative to it. MOCK_CHANGED is what merging the PR changes on the base; MOCK_TOUCHED what every PR commit
# touches. MOCK_SHALLOW=true makes the repository shallow until an --unshallow fetch, which fails with
# MOCK_UNSHALLOW_FAILS.
GIT = r"""
echo "git $*" >> "$MOCK_LOG"
emit() {  # $1: newline-separated paths; $2: set to list them as diff.relative=true would from the current directory
  sub=''
  if [ -n "$2" ]; then sub=$(pwd -P); sub=${sub#"$MOCK_ROOT"}; sub=${sub#/}; fi
  printf '%s\n' "$1" | while IFS= read -r f; do
    if [ -z "$sub" ]; then printf '%s\0' "$f"; else case $f in "$sub"/*) printf '%s\0' "${f#"$sub"/}" ;; esac; fi
  done
}
case "$*" in
  "rev-parse --show-toplevel") echo "$MOCK_ROOT" ;;
  "-C . rev-parse --path-format=absolute --git-common-dir") echo "$MOCK_ROOT/.git" ;;
  "-C $MOCK_SOURCE rev-parse --path-format=absolute --git-common-dir") echo "$MOCK_SOURCE_COMMON" ;;
  "-C . remote get-url origin") echo "$MOCK_ORIGIN" ;;
  "-C $MOCK_SOURCE remote get-url origin")
    if [ -n "$MOCK_SOURCE_ORIGIN" ]; then echo "$MOCK_SOURCE_ORIGIN"; else echo "error: No such remote" >&2; exit 2; fi ;;
  "fetch -q --no-tags origin +refs/heads/main:refs/remotes/origin/main")
    [ -z "$MOCK_FETCH_FAILS" ] || { echo "fatal: unable to access the remote" >&2; exit 128; } ;;
  "rev-parse --verify refs/remotes/origin/main^{commit}") echo "$MOCK_BASE_SHA" ;;
  "ls-tree --full-tree $MOCK_BASE_SHA -- .claude/kaizen-managed")
    if [ -n "$MOCK_LIST_ENTRY" ]; then printf '%s\t.claude/kaizen-managed\n' "$MOCK_LIST_ENTRY"
    elif [ -f "$MOCK_BASE_LIST" ]; then printf '100644 blob listoid\t.claude/kaizen-managed\n'; fi ;;
  "cat-file blob listoid") cat "$MOCK_BASE_LIST" ;;
  "cat-file blob linkoid") printf '../elsewhere' ;;
  "cat-file -e $MOCK_HEAD^{commit}") ;;
  "rev-parse --is-shallow-repository") echo "${MOCK_SHALLOW:-false}" ;;
  "fetch -q --no-tags --unshallow origin +refs/heads/main:refs/remotes/origin/main refs/pull/7/head")
    [ -z "$MOCK_UNSHALLOW_FAILS" ] || { echo "fatal: the remote end hung up" >&2; exit 128; } ;;
  "log --format= --name-only -z --no-renames --no-relative --ignore-submodules=none --diff-merges=separate"*)
    emit "$MOCK_TOUCHED" ;;
  "log --format= --name-only -z --no-renames --ignore-submodules=none --diff-merges=separate"*)
    emit "$MOCK_TOUCHED" relative ;;
  "merge-tree --write-tree $MOCK_BASE_SHA $MOCK_HEAD")
    echo tree0
    [ -z "$MOCK_CONFLICT" ] || {
      printf '100644 x 2\tdraft.md\n\nCONFLICT (content): draft.md\n'
      echo "warning: merge-tree noise" >&2; exit 1; } ;;
  "diff --name-only -z --no-renames --no-relative --ignore-submodules=none $MOCK_BASE_SHA tree0")
    emit "$MOCK_CHANGED" ;;
  "diff --name-only -z --no-renames --ignore-submodules=none $MOCK_BASE_SHA tree0") emit "$MOCK_CHANGED" relative ;;
  *) echo "unexpected: git $*" >&2; exit 128 ;;
esac
"""


class MergePrManagedPathTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        # Keep PATH to this directory so only the stubs and these tools are reachable.
        for command in ("jq", "mktemp", "rm", "grep", "cat", "tr", "touch", "sleep", "sed"):
            path = shutil.which(command)
            self.assertIsNotNone(path, f"{command} is required")
            (self.bin / command).symlink_to(path)
        self.checkout = self.root / "checkout"
        (self.checkout / ".claude").mkdir(parents=True)
        (self.checkout / "home").mkdir()
        self.base_list = self.root / "base-list"
        self.base_list.write_text(MANAGED)
        self.env = {
            "PATH": str(self.bin),
            "HOME": str(self.root),
            "MOCK_LOG": str(self.root / "log"),
            "MOCK_HEAD": HEAD,
            "MOCK_BASE_SHA": BASE,
            "MOCK_ROOT": str(self.checkout),
            "MOCK_ORIGIN": "git@github.com:O/R.git",
            "MOCK_SOURCE": str(self.root / "source/home"),
            "MOCK_SOURCE_COMMON": str(self.root / "source/.git"),
            "MOCK_BASE_LIST": str(self.base_list),
            "MOCK_MERGED": str(self.root / "merged"),
            "MOCK_CHANGED": "README.md",
        }
        self.mock("gh", GH)
        self.mock("git", GIT)
        self.mock("chezmoi", '[ -z "$MOCK_CHEZMOI_FAILS" ] || exit 1\necho "$MOCK_SOURCE"')

    def mock(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def in_dotfiles(self):
        self.env["MOCK_SOURCE_COMMON"] = str(self.checkout / ".git")

    def run_merge(self, *changed, touched=None, cwd=None):
        """`changed`: what the merge changes on the base; `touched`: what each PR commit touches (default: the same)."""
        self.env["MOCK_CHANGED"] = "\n".join(changed)
        self.env["MOCK_TOUCHED"] = "\n".join(changed if touched is None else touched)
        (self.root / "merged").unlink(missing_ok=True)
        (self.root / "log").unlink(missing_ok=True)
        return subprocess.run([shutil.which("bash"), str(SCRIPT), "7", HEAD[:12]], env=self.env,
                              cwd=cwd or self.checkout, capture_output=True, text=True, timeout=30)

    def merged(self):
        return (self.root / "merged").exists()

    def assert_refused(self, result, message):
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn(message, result.stderr)
        self.assertFalse(self.merged())

    def assert_merged(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"MERGED {HEAD} 123456789\n")
        self.assertTrue(self.merged())

    def assert_owner_only(self, result, path):
        self.assert_refused(result, "only the owner merges it")
        self.assertIn("enabling auto-merge on the checked head", result.stderr)
        self.assertIn(path, result.stderr.splitlines())

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

    def test_full_paths_from_a_subdirectory(self):
        managed = "home/dot_claude/CLAUDE.md"
        for source, changed, touched in (("commits", "README.md", managed), ("merge result", managed, "README.md")):
            with self.subTest(source=source):
                self.assert_owner_only(self.run_merge(changed, touched=(touched,), cwd=self.checkout / "home"), managed)

    def test_dotfiles_refuses_when_the_base_has_no_list(self):
        self.base_list.unlink()
        for clone in ("worktree of the source", "separate clone"):
            with self.subTest(clone=clone):
                if clone == "worktree of the source":
                    self.in_dotfiles()
                else:  # another git common dir, but the source's origin is the repository gh merges
                    self.env["MOCK_SOURCE_COMMON"] = str(self.root / "source/.git")
                    self.env["MOCK_SOURCE_ORIGIN"] = "https://github.com/O/r/"
                self.assert_refused(self.run_merge("README.md"), "origin/main has no .claude/kaizen-managed")

    def test_refuses_a_list_that_is_not_a_regular_file(self):
        for entry in ("040000 tree treeoid", "120000 blob linkoid"):
            with self.subTest(entry=entry):
                self.env["MOCK_LIST_ENTRY"] = entry
                self.assert_refused(self.run_merge("home/dot_claude/CLAUDE.md"), "is not a regular file")

    def test_refuses_when_the_chezmoi_source_is_unknown(self):
        self.env["MOCK_CHEZMOI_FAILS"] = "1"
        self.base_list.unlink()
        self.assert_refused(self.run_merge("README.md"), "could not resolve the chezmoi source")

    def test_origin_must_be_the_repository_gh_merges(self):
        self.env["MOCK_ORIGIN"] = "https://github.com/someone/r.git"
        self.assert_merged(self.run_merge("README.md"))  # elsewhere, as before the list existed
        self.in_dotfiles()
        self.assert_refused(self.run_merge("README.md"), "origin is 'someone/r' but gh resolves o/r")

    def test_fetch_failure_refuses_only_in_dotfiles(self):
        self.env["MOCK_FETCH_FAILS"] = "1"
        result = self.run_merge("home/dot_claude/CLAUDE.md")
        self.assert_merged(result)
        self.assertEqual(result.stderr, "")
        self.in_dotfiles()
        self.assert_refused(self.run_merge("README.md"),
                            "could not fetch origin/main: fatal: unable to access the remote, so PR 7 is not merged")

    def test_refuses_when_the_base_changes_before_the_merge(self):
        for name, value, message in (("MOCK_BASE_NOW", "dev", "retargeted from main to dev"),
                                     ("MOCK_BASE_SHA_NOW", "c" * 40, f"main moved from {BASE}")):
            with self.subTest(change=name):
                self.env[name] = value
                self.assert_refused(self.run_merge("README.md"), message)
                del self.env[name]

    def test_refuses_a_managed_path_touched_by_any_commit(self):
        for case, touched in (
                # B edits the list, H reverts B: the net diff against the base is README only.
                ("reverted change", ("README.md", ".claude/kaizen-managed", ".claude/kaizen-managed")),
                # -m lists a merge's changes against each parent; the second parent's side touched a managed file.
                ("merge commit", ("README.md", "home/dot_claude/CLAUDE.md", "README.md"))):
            with self.subTest(case=case):
                self.assert_owner_only(self.run_merge("README.md", touched=touched), touched[1])

    def git_calls(self, prefix):
        return [line for line in (self.root / "log").read_text().splitlines() if line.startswith(f"git {prefix}")]

    def test_listings_ignore_local_settings(self):
        self.assert_merged(self.run_merge("README.md"))
        log, diff = self.git_calls("log "), self.git_calls("diff ")
        self.assertEqual((len(log), len(diff)), (1, 1))
        for flag in (" --diff-merges=separate ", " --no-show-signature ", " --ignore-submodules=none "):
            self.assertIn(flag, log[0])
        self.assertIn(" --ignore-submodules=none ", diff[0])

    def test_shallow_clone_is_unshallowed_once_before_the_checks(self):
        self.in_dotfiles()
        self.env["MOCK_SHALLOW"] = "true"
        self.assert_merged(self.run_merge("README.md"))
        calls = (self.root / "log").read_text().splitlines()
        unshallow = [i for i, line in enumerate(calls) if "--unshallow" in line]
        self.assertEqual(len(unshallow), 1)
        self.assertIn("+refs/heads/main:refs/remotes/origin/main refs/pull/7/head", calls[unshallow[0]])
        checks = [i for i, line in enumerate(calls) if line.startswith(("git log ", "git merge-tree "))]
        self.assertEqual(len(checks), 2)
        self.assertLess(unshallow[0], min(checks))

    def test_unshallow_failure_refuses_only_in_dotfiles(self):
        self.env.update(MOCK_SHALLOW="true", MOCK_UNSHALLOW_FAILS="1")
        result = self.run_merge("home/dot_claude/CLAUDE.md")
        self.assert_merged(result)  # elsewhere, as before the list existed
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.git_calls("log ") + self.git_calls("merge-tree "), [])
        self.in_dotfiles()
        self.assert_refused(self.run_merge("README.md"),
                            "could not fetch the full history for PR 7: fatal: the remote end hung up")

    def test_complete_clone_is_not_unshallowed(self):
        self.in_dotfiles()
        self.assert_merged(self.run_merge("README.md"))
        self.assertNotIn("--unshallow", (self.root / "log").read_text())

    def test_refuses_a_merge_result_in_a_managed_path(self):
        self.in_dotfiles()  # the base renamed draft.md into a managed path; the PR edits only draft.md
        self.assert_owner_only(self.run_merge("home/dot_claude/CLAUDE.md", touched=("draft.md",)),
                               "home/dot_claude/CLAUDE.md")

    def test_conflict_refuses_only_in_dotfiles(self):
        self.env["MOCK_CONFLICT"] = "1"
        result = self.run_merge("README.md")
        self.assert_merged(result)
        self.assertEqual(result.stderr, "")
        self.in_dotfiles()
        self.assert_refused(self.run_merge("README.md"),
                            "GitHub cannot merge it cleanly either: warning: merge-tree noise")

    def test_unmanaged_multi_commit_pr_merges(self):
        self.in_dotfiles()
        self.assert_merged(self.run_merge("README.md", "docs/setup.md", touched=(
            "README.md", "docs/setup.md", "README.md", "home/dot_config/git/config", "home/dot_config/git/config")))

    def test_unmanaged_paths_merge(self):
        self.in_dotfiles()
        self.assert_merged(self.run_merge("README.md", "home/dot_config/git/config", "scripts/chezmoi-plan.sh",
                                          "docs/kaizen-notes.md", "home/.chezmoiexternal.toml"))

    def test_other_repository_without_a_list_merges(self):
        self.base_list.unlink()
        self.assert_merged(self.run_merge("home/dot_claude/CLAUDE.md"))


if __name__ == "__main__":
    unittest.main()
