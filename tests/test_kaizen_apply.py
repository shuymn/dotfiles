"""Tests of scripts/kaizen/apply.py. No real git: the core reads a fixture Repo through the reader interface, and the
mirror's clone/fetch run a fake `git` on PATH that records argv and environment. Writer tests use real files in temp
dirs and the real renameatx_np; on Darwin they fail when it is unavailable, elsewhere they skip."""
from pathlib import Path
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(f"test_kaizen_{name}", REPO / f"scripts/kaizen/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


apply = load("apply")
DARWIN = sys.platform == "darwin"
writer = unittest.skipUnless(DARWIN, "renameatx_np is macOS only")

SKILL = "home/dot_claude/skills/hiden/SKILL.md"
REF = "home/dot_claude/skills/hiden/references/a.md"
AGENT = "home/dot_claude/agents/w.md"
EDITED = "home/dot_claude/skills/hiden/references/orchestration.md"
T_SKILL, T_REF, T_AGENT, T_EDITED = (apply.plain_target(p) for p in (SKILL, REF, AGENT, EDITED))
BASE = {
    ".chezmoiroot": b"home\n",
    ".chezmoi.toml.tmpl": b"[data]\n",
    ".claude/kaizen-managed": b"home/dot_claude/**\nhome/.chezmoiignore\nhome/.chezmoiremove\nscripts/kaizen/**\n"
                              b"docs/kaizen.md\n.claude/kaizen-managed\n",
    "home/.chezmoiignore": b"# local\n.config/age/**\n",
    "home/.chezmoiremove": b".tmux.conf\n.claude/agents/old.md\n",
    "home/dot_zshenv": b"export A=1\n",
    "home/dot_claude/hooks/x.py": b"print(1)\n",
    "docs/kaizen.md": b"doc\n",
    SKILL: b"skill v0\n",
    REF: b"ref v0\n",
    AGENT: b"agent v0\n",
    EDITED: b"orch v0\n",
}


class Repo:
    """A fixture git history behind the reader interface of apply.GitReader."""

    def __init__(self, tree=None):
        self.objects, self.n = {}, 0
        self.head = self.commit(tree or BASE, parent=None, subject="root")

    def commit(self, changes, subject="change", parent="head"):
        parent = self.head if parent == "head" else parent
        tree = dict(self.objects[parent]["tree"]) if parent else {}
        for path, value in changes.items():
            if value is None:
                tree.pop(path, None)
            else:
                tree[path] = value if isinstance(value, tuple) else ("100644", value)
        self.n += 1
        sha = hashlib.sha1(str(self.n).encode()).hexdigest()
        self.objects[sha] = {"parent": parent, "tree": tree, "subject": subject}
        return sha

    def main(self, changes, subject="change"):
        self.head = self.commit(changes, subject)
        return self.head

    def resolve(self, rev):
        if rev == "refs/heads/main":
            return self.head
        found = [s for s in self.objects if s.startswith(rev)]
        if len(found) != 1:
            raise apply.ApplyError(f"unknown revision {rev}")
        return found[0]

    def first_parents(self, head):
        rows, c = [], head
        while c:
            rows.append((c, self.objects[c]["parent"]))
            c = self.objects[c]["parent"]
        return rows

    def changes(self, parent, commit):
        a, b = self.objects[parent]["tree"], self.objects[commit]["tree"]
        out = []
        for path in sorted(set(a) | set(b)):
            if path not in a:
                out.append(("A", path))
            elif path not in b:
                out.append(("D", path))
            elif a[path] != b[path]:
                out.append(("M", path))
        return out

    def blob(self, commit, path):
        return self.objects[commit]["tree"].get(path)

    def names(self, commit, directory):
        prefix = directory + "/" if directory else ""
        return sorted({p[len(prefix):].split("/")[0] for p in self.objects[commit]["tree"] if p.startswith(prefix)})

    def files(self, commit, prefixes):
        return [(m, p) for p, (m, _) in sorted(self.objects[commit]["tree"].items()) if p.startswith(prefixes)]

    def subject(self, commit):
        return self.objects[commit]["subject"]


def make_home(repo, commit, home):
    """A live home at commit: every v1 target written with mode 0644."""
    for mode, path in repo.files(commit, apply.ROOTS):
        rel = apply.plain_target(path)
        if rel:
            target = Path(home) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(repo.blob(commit, path)[1])
            target.chmod(0o644)


def entry(merge, target, step, **extra):
    """A journal entry of the shape apply writes."""
    return {"run": "r", "merge": merge, "target": target, "backup": f"backup/r/{merge[:12]}/{target}",
            "expected_old_sha": "0" * 64, "new_sha": "1" * 64, "parent": None, "step": step, **extra}


def scenario():
    """Cursor L at the root, then a merge M changing two v1 targets (deterministic, so a child process rebuilds it)."""
    repo = Repo()
    L = repo.head
    M = repo.main({SKILL: b"skill v1\n", AGENT: b"agent v1\n"}, "Merge pull request #10 from x/y")
    return repo, L, M


@contextlib.contextmanager
def no_hang(seconds=10):
    """Fail the test instead of hanging it."""
    def stop(*_):
        raise AssertionError(f"still blocked after {seconds}s")
    old = signal.signal(signal.SIGALRM, stop)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.home = self.dir / "home"
        self.home.mkdir()
        self.state = apply.State(self.home)

    def setup(self, repo=None, at=None, cursor=True):
        if repo is None:
            repo, L, M = scenario()
        else:
            L, M = at, repo.head
        self.repo, self.L, self.M = repo, L, M
        make_home(repo, L, self.home)
        if cursor:
            self.state.write("applied.json", {"commit": L, "at": "t", "by": "owner", "run": None})
        return repo

    def run_apply(self, **kw):
        return apply.run(self.home, reader=self.repo, head=self.repo.head, **kw)

    def live(self, rel):
        return (self.home / rel).read_bytes()

    def inode(self, rel):
        return os.stat(self.home / rel).st_ino

    def backups(self, rel):
        return sorted(self.state.dir.glob(f"backup/*/*/{rel}"))

    def cursor(self):
        return (self.state.applied() or {}).get("commit")


# ---------------------------------------------------------------- eligibility, classification (pure)

class Eligibility(unittest.TestCase):
    def assess(self, changes, base=None):
        repo = Repo(base)
        P = repo.head
        M = repo.main(changes)
        return apply.assess(repo, P, M)

    def test_plain_modifications_are_applicable(self):
        targets, reason = self.assess({SKILL: b"new\n", AGENT: b"new\n"})
        self.assertIsNone(reason)
        self.assertEqual(sorted(targets), sorted([(AGENT, T_AGENT), (SKILL, T_SKILL)]))
        self.assertEqual(T_SKILL, ".claude/skills/hiden/SKILL.md")

    def test_anything_else_refuses_the_whole_merge(self):
        cases = {
            "added": {SKILL: b"new\n", "home/dot_claude/skills/hiden/new.md": b"x\n"},
            "deleted": {SKILL: b"new\n", REF: None},
            "managed list": {SKILL: b"new\n", ".claude/kaizen-managed": b"home/dot_claude/**\n"},
            "chezmoi helper": {SKILL: b"new\n", "scripts/host-data.sh": b"echo 2\n"},
            "repo-only lookalike": {SKILL: b"new\n", "docsx/a.md": b"x\n"},
            "hook": {SKILL: b"new\n", "home/dot_claude/hooks/x.py": b"print(2)\n"},
            "unmanaged": {SKILL: b"new\n", "home/dot_zshenv": b"export A=2\n"},
            "ignore file": {SKILL: b"new\n", "home/.chezmoiignore": b".config/age/**\n.x\n"},
        }
        for name, changes in cases.items():
            with self.subTest(name):
                self.assertIsNone(self.assess(changes)[0])
        targets, reason = self.assess(cases["hook"])
        self.assertIn("home/dot_claude/hooks/x.py", reason)

    def test_repo_only_paths_ride_along(self):
        changes = {SKILL: b"new\n", "docs/kaizen.md": b"doc 2\n", "tests/test_x.py": b"t\n",
                   "scripts/kaizen/apply.py": b"a\n", ".github/workflows/x.yml": b"w\n", "README.md": b"r\n",
                   "AGENTS.md": b"a\n", "CLAUDE.md": b"c\n"}
        targets, reason = self.assess(changes)
        self.assertIsNone(reason)
        self.assertEqual(targets, [(SKILL, T_SKILL)])
        self.assertEqual(self.assess({"docs/kaizen.md": b"doc 2\n"}), (None, "no change"))

    def test_attribute_names_and_templates_are_outside_v1(self):
        for path in ("home/dot_claude/skills/hiden/executable_x.sh", "home/dot_claude/skills/hiden/x.md.tmpl",
                     "home/dot_claude/skills/private_p/x.md", "home/dot_claude/agents/.hidden.md",
                     "home/dot_claude/skills/symlink_claude-recall.tmpl", "home/dot_claude/settings.json"):
            with self.subTest(path):
                base = {**BASE, path: b"a\n"}
                self.assertIsNone(apply.plain_target(path))
                self.assertIn("outside v1", self.assess({path: b"b\n"}, base)[1])

    def test_empty_or_whitespace_blob_refuses(self):
        self.assertIn("empty", self.assess({SKILL: b" \n\t\n"})[1])
        self.assertIn("empty", self.assess({SKILL: b"new\n"}, {**BASE, SKILL: b"\n"})[1])

    def test_mode_other_than_100644_refuses(self):
        self.assertIn("not a 100644 blob", self.assess({SKILL: ("100755", b"skill v0\n")})[1])

    def test_ignore_or_remove_line_matching_target_or_ancestor_refuses(self):
        for rules, line in (("home/.chezmoiremove", b".claude/skills/hiden/SKILL.md"),
                            ("home/.chezmoiignore", b".claude/skills"),
                            ("home/.chezmoiignore", b".claude/skills/*/SKILL.md"),
                            ("home/.chezmoiignore", b"**/SKILL.md")):
            with self.subTest(line=line):
                base = {**BASE, rules: BASE[rules] + line + b"\n"}
                reason = self.assess({SKILL: b"new\n"}, base)[1]
                self.assertIn(line.decode(), reason)

    def test_any_template_action_in_a_rule_file_refuses(self):
        for rules, text in (
                ("home/.chezmoiignore", b'{{- if eq .chezmoi.os "darwin" }}\n.config/x\n{{- else }}\n.config/y\n{{ end }}\n'),
                ("home/.chezmoiignore", b".claude/ag\n{{- /* join */ -}}\nents/w.md\n"),  # joins two lines into one rule
                ("home/.chezmoiignore.tmpl", b"{{- if true -}}\n.claude/ag\n{{ end }}ents/w.md\n"),
                ("home/.chezmoiremove", b"{{ .extra }}\n")):
            with self.subTest(rules=rules, text=text):
                reason = self.assess({AGENT: b"new\n"}, {**BASE, rules: text})[1]
                self.assertIn("template line", reason)

    def test_another_source_for_the_same_target_refuses(self):
        for other in ("home/dot_claude/skills/hiden/literal_SKILL.md", "home/dot_claude/skills/hiden/SKILL.md.tmpl",
                      "home/dot_claude/skills/exact_hiden/x.md", "home/private_dot_claude/y"):
            with self.subTest(other):
                self.assertIn("collides", self.assess({SKILL: b"new\n"}, {**BASE, other: b"x\n"})[1])

    def test_every_rule_file_spelling_is_read(self):
        for rules in (".chezmoiignore.tmpl", ".chezmoiremove.tmpl"):
            with self.subTest(rules):
                reason = self.assess({SKILL: b"new\n"}, {**BASE, f"home/{rules}": b".claude/skills/**\n"})[1]
                self.assertIn(f"home/{rules}", reason)
                nested = {**BASE, f"home/dot_claude/skills/{rules}": b"x\n"}
                self.assertIn("own ignore", self.assess({SKILL: b"new\n"}, nested)[1])

    def test_a_template_action_after_a_comment_mark_refuses(self):
        for line in (b'.config/x # {{ "\\n.claude/**" }}\n', b'# {{ .extra }}\n'):
            with self.subTest(line=line):
                reason = self.assess({SKILL: b"new\n"}, {**BASE, "home/.chezmoiignore": line})[1]
                self.assertIn("template line", reason)

    def test_pattern_syntax_the_matcher_lacks_refuses(self):
        for line in (b".claude/{skills,agents}/**", b".claude/[sa]*/**", b".claude/sk\\ills/**", b".config/{x}",
                     b".config/zz#.claude/skills/**"):
            with self.subTest(line=line):
                reason = self.assess({SKILL: b"new\n"}, {**BASE, "home/.chezmoiremove": line + b"\n"})[1]
                self.assertIn("unsupported pattern syntax", reason)

    def test_nested_ignore_file_or_external_refuses(self):
        self.assertIn("own ignore", self.assess({SKILL: b"new\n"},
                                                {**BASE, "home/dot_claude/skills/.chezmoiignore": b"x\n"})[1])
        self.assertIn(".chezmoiexternal", self.assess({SKILL: b"new\n"},
                                                      {**BASE, "home/.chezmoiexternal.toml": b"x\n"})[1])

    def test_mapping_guards(self):
        self.assertIn(".chezmoiroot", self.assess({SKILL: b"new\n"}, {**BASE, ".chezmoiroot": b"src\n"})[1])
        self.assertIn("umask", self.assess({SKILL: b"new\n"}, {**BASE, ".chezmoi.toml.tmpl": b"umask = 0o077\n"})[1])

    def test_candidates_are_commits_touching_managed_home_paths(self):
        repo = Repo()
        P = repo.head
        for changes, expected in (({"docs/kaizen.md": b"d2\n"}, False), ({"mise.lock": b"x\n"}, False),
                                  ({"home/dot_zshenv": b"x\n"}, False), ({REF: b"r\n"}, True),
                                  ({"home/.chezmoiremove": b"x\n"}, True)):
            with self.subTest(changes=list(changes)):
                M = repo.commit(changes, parent=P)
                self.assertEqual(apply.is_candidate(repo, P, M), expected)


class Classification(unittest.TestCase):
    OLD, NEW = b"old\n", b"new\n"

    def kind(self, live):
        return apply.kind(live, self.OLD, self.NEW)

    def test_done_write_conflict(self):
        f = lambda data, mode=0o644: {"type": "file", "mode": mode, "bytes": data}
        self.assertEqual(self.kind(f(self.NEW)), "done")
        self.assertEqual(self.kind(f(self.OLD)), "write")
        self.assertEqual(self.kind(f(b"edited\n")), "conflict")
        self.assertEqual(self.kind(f(self.OLD, 0o600)), "conflict")
        self.assertEqual(self.kind(f(self.NEW, 0o755)), "conflict")
        for t in ("missing", "symlink", "other", "parent"):
            self.assertEqual(self.kind({"type": t}), "conflict")

    def test_parsers(self):
        self.assertEqual(apply.parse_name_status(b"M\0home/a b\0D\0x\0"), [("M", "home/a b"), ("D", "x")])
        self.assertEqual(apply.parse_ls_tree(b"100644 blob abc\thome/x y\x00040000 tree def\thome/d\x00"),
                         [("100644", "blob", "abc", "home/x y"), ("040000", "tree", "def", "home/d")])

    def test_pattern_and_names(self):
        self.assertTrue(apply.pattern_match(".claude/**", ".claude/a/b"))
        self.assertFalse(apply.pattern_match("*.md", ".claude/a.md"))
        self.assertEqual(apply.target_name("private_dot_claude"), ".claude")
        self.assertEqual(apply.target_name("literal_dot_x"), "dot_x")
        self.assertEqual(apply.target_name("x.md.tmpl"), "x.md")


# ---------------------------------------------------------------- the chain

class Chain(Base):
    def test_non_managed_commits_pass_and_the_chain_stops_at_the_first_refused_candidate(self):
        repo = Repo()
        L = repo.head
        c1 = repo.main({"docs/kaizen.md": b"d2\n"}, "docs only")
        c2 = repo.main({"mise.lock": b"lock\n"}, "chore(deps): lock file maintenance (#996)")
        m3 = repo.main({REF: b"ref v1\n", "home/dot_claude/hooks/x.py": b"print(2)\n"}, "Merge pull request #3 from a")
        repo.main({SKILL: b"skill v1\n"}, "Merge pull request #4 from b")
        self.setup(repo, L)
        res = self.run_apply()
        self.assertEqual([(m["commit"], m["status"]) for m in res["merges"]], [(m3, "refused")])
        self.assertEqual(res["passed"], 2)
        self.assertEqual(self.cursor(), c2)  # past the passing commits, before the refused one
        self.assertEqual((self.live(T_REF), self.live(T_SKILL)), (b"ref v0\n", b"skill v0\n"))
        self.assertEqual(len(res["decisions"]), 1)
        self.assertIn("#3", res["decisions"][0])
        self.assertIn(f"cycle.py adopt {m3}", res["decisions"][0])
        self.assertNotIn(c1, json.dumps(res["merges"]))

    def test_live_already_at_a_later_main_version_is_done(self):
        repo = Repo()
        L = repo.head
        m1 = repo.main({SKILL: b"skill v1\n"}, "Merge pull request #1 from a")
        m2 = repo.main({SKILL: b"skill v2\n"}, "Merge pull request #2 from b")
        self.setup(repo, L)
        (self.home / T_SKILL).write_bytes(b"skill v2\n")  # another session applied main already
        before = self.inode(T_SKILL)
        res = self.run_apply()
        self.assertEqual([(m["commit"], m["status"]) for m in res["merges"]], [(m1, "done"), (m2, "done")])
        self.assertEqual(res["decisions"], [])
        self.assertEqual(self.cursor(), m2)
        self.assertEqual((self.live(T_SKILL), self.inode(T_SKILL)), (b"skill v2\n", before))

    def test_cursor_off_the_chain_is_an_error(self):
        repo = self.setup()
        side = repo.commit({REF: b"side\n"}, parent=self.L)
        self.state.write("applied.json", {"commit": side, "at": "t", "by": "owner", "run": None})
        res = self.run_apply()
        self.assertEqual(res["status"], "error")
        self.assertIn("not on main's first-parent chain", res["decisions"][0])
        self.assertEqual(self.live(T_SKILL), b"skill v0\n")

    def test_missing_baseline_writes_nothing_and_proposes_adopt(self):
        self.setup(cursor=False)
        make_home(self.repo, self.M, self.home)  # live is at main except one session edit
        (self.home / T_EDITED).write_bytes(b"live session edit\n")
        before = self.inode(T_EDITED)
        res = self.run_apply()
        self.assertEqual((res["status"], res["differing"]), ("baseline-missing", [T_EDITED]))
        self.assertIn(f"cycle.py adopt {self.M}", res["decisions"][0])
        self.assertEqual((self.live(T_EDITED), self.inode(T_EDITED)), (b"live session edit\n", before))
        self.assertIsNone(self.state.applied())

    def test_no_new_merge_after_the_budget(self):
        self.setup()
        res = self.run_apply(budget=-1)
        self.assertEqual((res["status"], res["merges"][0]["status"]), ("partial", "pending"))
        self.assertEqual(self.live(T_SKILL), b"skill v0\n")

    def test_invalid_state_writes_nothing_and_is_one_decision(self):
        for name, text in (("applied.json", '{"commit": "bad"}'), ("journal.json", "not json"),
                           ("journal.json", json.dumps({"entries": [{"merge": "x"}]})),
                           ("journal.json", json.dumps({"entries": [{**entry("b" * 40, T_AGENT, "clean"), "target": None}]})),
                           ("journal.json", json.dumps({"entries": [entry("b" * 40, T_AGENT, "clean", note="\ud800")]})),
                           ("journal.json", json.dumps({"entries": [entry("b" * 40, "../x", "clean")]})),
                           ("journal.json", json.dumps({"entries": [entry("b" * 40, "a\0b", "clean")]})),
                           ("journal.json", json.dumps({"entries": [entry("b" * 40, T_AGENT, "clean", parent=[True, 1])]})),
                           ("applied.json", json.dumps({"commit": "a" * 40, "at": 1, "by": "owner"}))):
            with self.subTest(name=name, text=text):
                self.setup()
                (self.state.dir / name).write_text(text)
                res = self.run_apply()
                self.assertEqual(res["status"], "error")
                self.assertEqual(len(res["decisions"]), 1)
                self.assertIn("state invalid", res["decisions"][0])
                self.assertEqual(self.live(T_SKILL), b"skill v0\n")
                self.assertIn("state_error", apply.persisted(self.home))
                (self.state.dir / name).unlink()

    def test_a_fifo_or_symlink_is_invalid_state_and_one_bad_file_does_not_hide_the_other(self):
        self.setup()
        os.mkfifo(self.state.dir / "journal.json")
        with no_hang():
            res = self.run_apply()
        self.assertEqual(res["status"], "error")
        self.assertIn("not a regular file", res["decisions"][0])
        self.assertEqual(res["cursor"]["commit"], self.L)  # the cursor still reads
        (self.state.dir / "journal.json").unlink()
        (self.state.dir / "journal.json").symlink_to(self.dir / "elsewhere.json")
        (self.dir / "elsewhere.json").write_text('{"entries": []}')
        self.assertIn("unreadable", self.run_apply()["decisions"][0])
        self.assertEqual(self.live(T_SKILL), b"skill v0\n")

    def test_a_cursor_that_cannot_be_decoded_does_not_hide_the_journal(self):
        self.setup()
        self.state.save_journal([entry(self.M, T_AGENT, "unresolved", note="swapped back")])
        (self.state.dir / "applied.json").write_text("[" * 100000 + "]" * 100000)
        res = self.run_apply()
        self.assertEqual(res["status"], "error")
        self.assertEqual([e["target"] for e in res["journal"]], [T_AGENT])
        self.assertTrue(any("applied.json" in d for d in res["decisions"]))  # "not JSON", or "not a cursor" where
        # the interpreter decodes this depth
        self.assertEqual(self.live(T_SKILL), b"skill v0\n")

    def test_a_subject_that_is_not_utf8_is_still_read(self):
        reader = apply.GitReader("/nonexistent", "git", {}, 0)
        reader._git = lambda *args: b"Merge pull request #2 \xff\n"
        self.assertEqual(reader.subject("c" * 40), "Merge pull request #2 \ufffd")

    def test_lock_held_still_reports_the_cursor_and_the_journal(self):
        self.setup()
        self.state.save_journal([entry(self.M, T_AGENT, "unresolved", note="swapped back")])
        held = self.state.lock()
        self.addCleanup(held.close)
        res = self.run_apply()
        self.assertEqual(res["status"], "skipped")
        self.assertEqual((res["cursor"]["commit"], [e["target"] for e in res["journal"]]), (self.L, [T_AGENT]))
        self.assertEqual(len(res["decisions"]), 1)
        self.assertIn(f"~/{T_AGENT}", res["decisions"][0])
        self.assertIn(str(self.state.dir / "backup/r"), res["decisions"][0])

    def test_the_cursor_reported_after_a_failed_journal_write_is_the_one_on_disk(self):
        self.setup()
        make_home(self.repo, self.M, self.home)  # every target done: the cursor advances, then the journal is saved
        real = apply.State.save_journal

        def full(state, entries):
            if (state.applied() or {}).get("commit") == self.M:
                raise OSError(28, "No space left on device")
            return real(state, entries)
        with mock.patch.object(apply.State, "save_journal", full):
            res = self.run_apply()
        self.assertEqual(res["status"], "error")
        self.assertIn("No space left", res["reason"])
        self.assertEqual((res["cursor"]["commit"], self.cursor()), (self.M, self.M))

    def test_lock_held_skips(self):
        self.setup()
        held = self.state.lock()
        self.addCleanup(held.close)
        self.assertEqual(self.run_apply()["status"], "skipped")
        self.assertEqual(self.live(T_SKILL), b"skill v0\n")

    def test_check_writes_nothing(self):
        self.setup()
        (self.home / T_SKILL).write_bytes(b"edited\n")
        before = {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        res = self.run_apply(check=True)
        self.assertEqual(res["merges"][0]["status"], "conflict")
        self.assertEqual(res["status"], "would stop")
        self.assertEqual({p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()}, before)


# ---------------------------------------------------------------- writes (real renameatx_np)

@writer
class Swap(Base):
    def test_swap_exchanges_two_entries(self):
        (self.dir / "a").write_text("A")
        (self.dir / "b").write_text("B")
        fd = os.open(self.dir, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        apply.exchange(fd, "a", fd, "b")  # fails, not skips, on Darwin without renameatx_np
        self.assertEqual(((self.dir / "a").read_text(), (self.dir / "b").read_text()), ("B", "A"))

    def test_clean_merge_swaps_old_inodes_into_the_backup(self):
        self.setup()
        (self.home / T_EDITED).write_bytes(b"untouched drift\n")  # not a target of M: never blocks it
        olds = {t: self.inode(t) for t in (T_SKILL, T_AGENT)}
        untouched = self.inode(T_REF)
        res = self.run_apply()
        self.assertEqual((res["status"], res["merges"][0]["status"]), ("ok", "applied"))
        self.assertEqual(res["merges"][0]["targets"], {T_AGENT: "written", T_SKILL: "written"})
        for t, old in ((T_SKILL, b"skill v0\n"), (T_AGENT, b"agent v0\n")):
            [backup] = self.backups(t)
            self.assertEqual(os.stat(backup).st_ino, olds[t])  # the displaced inode itself, by name
            self.assertEqual(backup.read_bytes(), old)
            self.assertEqual(os.stat(self.home / t).st_mode & 0o7777, 0o644)
        self.assertEqual((self.live(T_SKILL), self.live(T_AGENT)), (b"skill v1\n", b"agent v1\n"))
        self.assertEqual(self.inode(T_REF), untouched)
        self.assertEqual(self.live(T_EDITED), b"untouched drift\n")
        self.assertEqual(self.state.applied()["commit"], self.M)
        self.assertEqual(self.state.applied()["by"], "cycle")
        self.assertEqual((self.state.journal(), res["decisions"]), ([], []))

    def test_done_targets_are_not_written(self):
        self.setup()
        (self.home / T_AGENT).write_bytes(b"agent v1\n")  # the owner already applied this one
        agent = self.inode(T_AGENT)
        res = self.run_apply()
        self.assertEqual(res["merges"][0]["targets"], {T_AGENT: "done", T_SKILL: "written"})
        self.assertEqual(self.inode(T_AGENT), agent)
        self.assertEqual(self.backups(T_AGENT), [])
        self.assertEqual(self.cursor(), self.M)

    def test_all_done_advances_the_cursor_as_observed(self):
        self.setup()
        make_home(self.repo, self.M, self.home)
        res = self.run_apply()
        self.assertEqual(res["merges"][0]["status"], "done")
        self.assertEqual((self.cursor(), self.state.applied()["by"]), (self.M, "observed"))

    def test_live_edit_on_a_target_refuses_the_whole_merge(self):
        self.setup()
        (self.home / T_SKILL).write_bytes(b"live edit\n")
        inodes = {t: self.inode(t) for t in (T_SKILL, T_AGENT)}
        res = self.run_apply()
        self.assertEqual(res["merges"][0]["status"], "conflict")
        self.assertEqual(res["merges"][0]["targets"], {T_AGENT: "write", T_SKILL: "conflict: edited"})
        self.assertEqual((self.live(T_SKILL), self.live(T_AGENT)), (b"live edit\n", b"agent v0\n"))
        self.assertEqual({t: self.inode(t) for t in inodes}, inodes)
        self.assertEqual(self.cursor(), self.L)
        self.assertEqual(len(res["decisions"]), 1)
        self.assertIn(T_SKILL, res["decisions"][0])

    def test_symlinked_parent_is_a_conflict_and_nothing_is_written(self):
        self.setup()
        real = self.dir / "elsewhere"
        shutil.move(self.home / ".claude/agents", real)
        (self.home / ".claude/agents").symlink_to(real)
        res = self.run_apply()
        self.assertIn("symlinked", res["merges"][0]["targets"][T_AGENT])
        self.assertEqual(((real / "w.md").read_bytes(), self.live(T_SKILL)), (b"agent v0\n", b"skill v0\n"))
        self.assertEqual(self.cursor(), self.L)

    def editor_save(self, rel, data):
        """What an editor does: write a new file and rename it over the target."""
        tmp = (self.home / rel).with_name(".edit.tmp")
        tmp.write_bytes(data)
        tmp.chmod(0o644)
        os.rename(tmp, self.home / rel)
        return os.stat(self.home / rel).st_ino

    def patch_exchange(self, before=None, after=None):
        real, calls = apply.exchange, []

        def wrapped(*a):
            calls.append(a)
            if before:
                before(len(calls))
            real(*a)
            if after:
                after(len(calls))
        return mock.patch.object(apply, "exchange", side_effect=wrapped), calls

    def test_editor_save_before_the_swap_is_swapped_back_and_both_kept(self):
        self.setup()
        edited = {}

        def save(n):
            if n == 1:
                edited["ino"] = self.editor_save(T_AGENT, b"editor version\n")
        patch, calls = self.patch_exchange(before=save)
        with patch:
            res = self.run_apply()
        self.assertTrue(edited)
        self.assertEqual(len(calls), 2)  # the swap and the swap-back, nothing after
        self.assertEqual((self.live(T_AGENT), self.inode(T_AGENT)), (b"editor version\n", edited["ino"]))
        [backup] = self.backups(T_AGENT)
        self.assertEqual(backup.read_bytes(), b"agent v1\n")
        [entry] = self.state.journal()
        self.assertEqual(entry["step"], "unresolved")
        self.assertIn("swapped back", entry["note"])
        self.assertEqual(self.cursor(), self.L)
        self.assertIn(str(backup), res["decisions"][0])
        self.assertEqual(self.live(T_SKILL), b"skill v0\n")  # agents/w.md sorts first; the stage stopped there
        self.assertEqual(self.run_apply()["status"], "blocked")

    def test_editor_rename_between_the_check_and_the_swap_back_stays_unresolved(self):
        self.setup()
        saved = {}

        def save(n):
            if n == 1:
                saved["y"] = self.editor_save(T_AGENT, b"version y\n")
            if n == 2:
                saved["z"] = self.editor_save(T_AGENT, b"version z\n")
        patch, _ = self.patch_exchange(before=save)
        with patch:
            self.run_apply()
        self.assertEqual(sorted(saved), ["y", "z"])
        [entry] = self.state.journal()
        self.assertEqual(entry["step"], "unresolved")
        self.assertIn("unverified", entry["note"])
        [backup] = self.backups(T_AGENT)
        self.assertEqual({self.live(T_AGENT), backup.read_bytes()}, {b"version y\n", b"version z\n"})
        self.assertEqual(self.cursor(), self.L)

    def move_and_recreate(self, rel, data):
        parent = (self.home / rel).parent
        os.rename(parent, parent.with_name(parent.name + ".moved"))
        parent.mkdir()
        (parent / Path(rel).name).write_bytes(data)
        (parent / Path(rel).name).chmod(0o644)
        return parent.with_name(parent.name + ".moved")

    def test_parent_moved_and_recreated_after_the_walk_refuses_before_the_swap(self):
        self.setup()
        real, moved = apply.stage_backup, {}

        def stage(*a):
            ino = real(*a)
            moved["dir"] = self.move_and_recreate(T_AGENT, b"agent v0\n")
            return ino
        patch, calls = self.patch_exchange()
        with mock.patch.object(apply, "stage_backup", side_effect=stage), patch:
            res = self.run_apply()
        self.assertTrue(moved)
        self.assertEqual(calls, [])
        self.assertEqual(((moved["dir"] / "w.md").read_bytes(), self.live(T_AGENT)), (b"agent v0\n", b"agent v0\n"))
        self.assertEqual(self.state.journal(), [])
        self.assertEqual(self.backups(T_AGENT), [])  # our staged file is removed, nothing else
        self.assertIn("parent changed before the swap", res["decisions"][0])
        self.assertEqual(self.cursor(), self.L)

    def test_parent_moved_after_the_swap_is_found_before_the_cursor_advances(self):
        self.setup()
        moved = {}

        def move(n):
            if n == 1:
                moved["dir"] = self.move_and_recreate(T_AGENT, b"agent v1\n")
        patch, _ = self.patch_exchange(after=move)
        with patch:
            self.run_apply()
        self.assertTrue(moved)
        [entry] = self.state.journal()
        self.assertEqual((entry["step"], entry["note"]), ("unresolved", "parent changed after the swap"))
        self.assertEqual(self.cursor(), self.L)

    def test_a_change_after_the_write_holds_the_cursor(self):
        self.setup()

        def touch(n):
            if n == 2:  # while the second target is written, the first one changes
                self.editor_save(T_AGENT, b"changed after apply\n")
        patch, _ = self.patch_exchange(after=touch)
        with patch:
            res = self.run_apply()
        self.assertEqual(res["merges"][0]["status"], "changed after apply")
        self.assertEqual(self.cursor(), self.L)
        self.assertEqual([e["step"] for e in self.state.journal() if e["target"] == T_AGENT], ["unresolved"])

    def test_partial_merge_resumes_and_revalidates_its_journal(self):
        self.setup()
        real, n = apply.stage_backup, []

        def stage(*a):
            ino = real(*a)
            n.append(1)
            if len(n) == 2:
                self.move_and_recreate(T_SKILL, b"skill v0\n")
            return ino
        with mock.patch.object(apply, "stage_backup", side_effect=stage):
            res = self.run_apply()
        self.assertEqual(res["merges"][0]["status"], "partial")
        self.assertEqual([(e["target"], e["step"]) for e in self.state.journal()], [(T_AGENT, "clean")])
        self.assertEqual(self.cursor(), self.L)
        res = self.run_apply()
        self.assertEqual(res["merges"][0]["targets"], {T_AGENT: "done", T_SKILL: "written"})
        self.assertEqual((self.cursor(), self.state.journal()), (self.M, []))

    def test_a_clean_entry_whose_parent_changed_is_not_trusted_on_restart(self):
        self.setup()
        real, n = apply.stage_backup, []

        def stage(*a):
            ino = real(*a)
            n.append(1)
            if len(n) == 2:
                self.move_and_recreate(T_SKILL, b"skill v0\n")
            return ino
        with mock.patch.object(apply, "stage_backup", side_effect=stage):
            self.run_apply()
        self.move_and_recreate(T_AGENT, b"agent v1\n")  # same bytes, another directory
        res = self.run_apply()
        self.assertEqual((res["status"], res["merges"][0]["status"]), ("blocked", "blocked"))
        self.assertEqual(self.cursor(), self.L)
        self.assertEqual([(e["target"], e["step"]) for e in self.state.journal()], [(T_AGENT, "unresolved")])
        self.assertEqual(self.live(T_SKILL), b"skill v0\n")

    def partial(self):
        """Run until the agent target is written and the skill step refuses (its parent changed before the swap)."""
        real, n = apply.stage_backup, []

        def stage(*a):
            ino = real(*a)
            n.append(1)
            if len(n) == 2:
                self.move_and_recreate(T_SKILL, b"skill v0\n")
            return ino
        with mock.patch.object(apply, "stage_backup", side_effect=stage):
            self.run_apply()
        self.assertEqual([(e["target"], e["step"]) for e in self.state.journal()], [(T_AGENT, "clean")])

    def test_an_owner_edit_after_a_partial_write_is_not_overwritten(self):
        self.setup()
        self.partial()
        (self.home / T_AGENT).write_bytes(b"agent v0\n")  # the owner puts the old version back
        ino = self.inode(T_AGENT)
        res = self.run_apply()
        self.assertEqual(res["status"], "blocked")
        self.assertEqual((self.live(T_AGENT), self.inode(T_AGENT)), (b"agent v0\n", ino))
        self.assertEqual(self.live(T_SKILL), b"skill v0\n")
        [e] = self.state.journal()
        self.assertEqual(e["step"], "unresolved")
        self.assertEqual(self.cursor(), self.L)
        self.assertIn(T_AGENT, res["decisions"][0])

    def test_a_written_target_restored_just_before_classification_is_not_rewritten(self):
        self.setup()
        self.partial()
        real = apply.Run.classify

        def restore_then_classify(run, *a):  # the window right before the snapshot that builds the write set
            (self.home / T_AGENT).write_bytes(b"agent v0\n")
            return real(run, *a)
        ino = self.inode(T_AGENT)  # restored in place below, so the inode stays unless something swaps it
        with mock.patch.object(apply.Run, "classify", restore_then_classify):
            res = self.run_apply()
        self.assertEqual(res["status"], "blocked")
        self.assertEqual(res["merges"][0]["targets"][T_AGENT], "journal: edited")
        self.assertEqual((self.live(T_AGENT), self.inode(T_AGENT)), (b"agent v0\n", ino))
        self.assertEqual(self.live(T_SKILL), b"skill v0\n")
        self.assertEqual([e["step"] for e in self.state.journal()], ["unresolved"])
        self.assertEqual(self.cursor(), self.L)

    def test_a_clean_entry_of_the_cursor_is_dropped_and_the_run_goes_on(self):
        self.setup()
        make_home(self.repo, self.M, self.home)  # the cursor advanced to M; the run died before clearing the journal
        self.state.write("applied.json", {"commit": self.M, "at": "t", "by": "cycle", "run": "r"})
        self.state.save_journal([entry(self.M, T_AGENT, "clean")])
        nxt = self.repo.main({REF: b"ref v1\n"}, "Merge pull request #11")
        res = self.run_apply()
        self.assertEqual((res["status"], res["merges"][0]["status"]), ("ok", "applied"))
        self.assertEqual((self.state.journal(), self.cursor()), ([], nxt))

    def test_a_displaced_inode_with_another_mode_is_not_accepted(self):
        self.setup()
        patch, calls = self.patch_exchange(before=lambda n: os.chmod(self.home / T_AGENT, 0o600) if n == 1 else None)
        with patch:
            self.run_apply()
        self.assertEqual(len(calls), 2)  # swapped and swapped back
        [e] = self.state.journal()
        self.assertEqual(e["step"], "unresolved")
        self.assertEqual(os.stat(self.home / T_AGENT).st_mode & 0o777, 0o600)
        self.assertEqual(self.live(T_AGENT), b"agent v0\n")
        self.assertEqual(self.cursor(), self.L)

    def test_a_third_version_makes_the_clean_entry_unresolved(self):
        self.setup()
        self.partial()
        (self.home / T_AGENT).write_bytes(b"a third version\n")
        res = self.run_apply()
        self.assertEqual(res["status"], "blocked")
        self.assertEqual([e["step"] for e in self.state.journal()], ["unresolved"])
        self.assertEqual(self.live(T_AGENT), b"a third version\n")
        self.assertEqual(self.cursor(), self.L)

    def test_the_stage_deadline_stops_between_target_steps(self):
        self.setup()
        patch, calls = self.patch_exchange(after=lambda n: time.sleep(1.2) if n == 1 else None)
        with patch:
            res = apply.run(self.home, reader=self.repo, head=self.repo.head, deadline=time.monotonic() + 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual((res["status"], res["merges"][0]["status"]), ("partial", "partial"))
        self.assertEqual([(e["target"], e["step"]) for e in self.state.journal()], [(T_AGENT, "clean")])
        self.assertEqual((self.live(T_AGENT), self.live(T_SKILL)), (b"agent v1\n", b"skill v0\n"))
        self.assertEqual(self.cursor(), self.L)
        self.assertEqual(res["decisions"], [])
        res = self.run_apply()  # the next run finishes it
        self.assertEqual((res["merges"][0]["status"], self.cursor()), ("applied", self.M))

    def test_a_parent_moved_after_the_final_walk_is_swapped_into_the_moved_dir_and_held(self):
        self.setup()
        moved = {}
        parent = (self.home / T_AGENT).parent

        def exchange_after_move(n):
            if n == 1:  # after the final walk and its identity check, before the syscall
                moved["dir"] = self.move_and_recreate(T_AGENT, b"agent v0\n")
        patch, calls = self.patch_exchange(before=exchange_after_move)
        with patch:
            res = self.run_apply()
        self.assertTrue(moved)
        self.assertEqual(len(calls), 1)
        self.assertEqual((moved["dir"] / "w.md").read_bytes(), b"agent v1\n")  # the swap landed in the moved dir
        self.assertEqual((parent / "w.md").read_bytes(), b"agent v0\n")  # the recreated one is untouched
        [backup] = self.backups(T_AGENT)
        self.assertEqual(backup.read_bytes(), b"agent v0\n")  # the displaced inode, named
        [e] = self.state.journal()
        self.assertEqual((e["step"], e["note"]), ("unresolved", "parent changed after the swap"))
        self.assertEqual(self.cursor(), self.L)
        self.assertIn(str(backup), res["decisions"][0])

    def test_sigterm_during_a_step_completes_the_step(self):
        self.setup()
        old = signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
        self.addCleanup(signal.signal, signal.SIGTERM, old)
        patch, calls = self.patch_exchange(before=lambda n: os.kill(os.getpid(), signal.SIGTERM))
        with patch, self.assertRaises(SystemExit):
            self.run_apply()
        self.assertEqual(len(calls), 1)
        [entry] = self.state.journal()
        self.assertEqual((entry["target"], entry["step"]), (T_AGENT, "clean"))
        self.assertEqual(self.live(T_AGENT), b"agent v1\n")
        self.assertEqual(self.cursor(), self.L)
        res = self.run_apply()  # the next run revalidates the entry and finishes the merge
        self.assertEqual(res["merges"][0]["targets"], {T_AGENT: "done", T_SKILL: "written"})
        self.assertEqual(self.cursor(), self.M)

    def test_kill_after_the_swap_blocks_until_resolve_then_resumes(self):
        self.setup()
        code = f"""
import os, signal, sys
sys.path.insert(0, {str(TESTS)!r})
import test_kaizen_apply as t
repo, L, M = t.scenario()
real = t.apply.exchange
def swap_then_die(*a):
    real(*a)
    os.kill(os.getpid(), signal.SIGKILL)
t.apply.exchange = swap_then_die
t.apply.run({str(self.home)!r}, reader=repo, head=repo.head)
"""
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, -signal.SIGKILL, p.stderr)
        [entry] = self.state.journal()
        self.assertEqual((entry["target"], entry["step"]), (T_AGENT, "staged"))
        self.assertEqual(self.live(T_AGENT), b"agent v1\n")
        [backup] = self.backups(T_AGENT)
        self.assertEqual(backup.read_bytes(), b"agent v0\n")

        res = self.run_apply()
        self.assertEqual((res["status"], self.cursor()), ("blocked", self.L))
        self.assertIn(str(backup), res["decisions"][0])
        self.assertIn(f"~/{T_AGENT}", res["decisions"][0])
        self.assertEqual(self.live(T_SKILL), b"skill v0\n")

        files = lambda: {p: (p.read_bytes(), p.stat().st_ino) for p in [self.home / T_AGENT, backup]}
        before, applied = files(), self.state.applied()
        out = []
        self.assertEqual(apply.resolve(self.home, out=out.append)["cleared"], False)
        self.assertEqual(len(self.state.journal()), 1)
        self.assertIn(T_AGENT, "\n".join(out))
        lines = {l.split()[0]: l for l in out if l.startswith("  ")}  # full SHA-256 of both paths
        self.assertTrue(lines["live"].endswith(hashlib.sha256(b"agent v1\n").hexdigest()), lines["live"])
        self.assertTrue(lines["backup"].endswith(hashlib.sha256(b"agent v0\n").hexdigest()), lines["backup"])
        self.assertEqual(apply.resolve(self.home, yes=True, out=out.append)["cleared"], True)
        self.assertEqual((self.state.journal(), files(), self.state.applied()), ([], before, applied))

        res = self.run_apply()
        self.assertEqual(res["merges"][0]["targets"], {T_AGENT: "done", T_SKILL: "written"})
        self.assertEqual(self.cursor(), self.M)


# ---------------------------------------------------------------- adopt

class Adopt(Base):
    def adopt(self, sha):
        out = []
        return apply.adopt(self.home, None, sha, reader=self.repo, head=self.repo.head, out=out.append), out

    def test_refuses_with_an_unresolved_journal(self):
        self.setup()
        self.state.save_journal([entry(self.M, T_SKILL, "staged")])
        with self.assertRaisesRegex(apply.ApplyError, "unresolved"):
            self.adopt(self.M)
        self.assertEqual(self.cursor(), self.L)

    def test_refuses_off_chain_and_not_after_the_cursor(self):
        repo = self.setup()
        side = repo.commit({REF: b"side\n"}, parent=self.L)
        for sha in (side, self.L):
            with self.subTest(sha=sha), self.assertRaises(apply.ApplyError):
                self.adopt(sha)
        self.assertEqual(self.cursor(), self.L)

    def test_prints_what_it_skips_and_records_the_owner(self):
        repo = Repo()
        L = repo.head
        m1 = repo.main({AGENT: b"agent v1\n", "docs/kaizen.md": b"d\n"}, "Merge pull request #1")
        m2 = repo.main({SKILL: b"skill v1\n", "home/dot_claude/hooks/x.py": b"print(3)\n"}, "Merge pull request #2")
        self.setup(repo, L)
        result, out = self.adopt(m2[:10])
        text = "\n".join(out)
        self.assertIn(f"skips {m1[:8]}", text)
        self.assertIn(f"{T_AGENT}: write", text)
        self.assertIn("other paths: docs/kaizen.md", text)
        self.assertIn("refused: outside v1: home/dot_claude/hooks/x.py", text)
        self.assertIn(f"{T_SKILL}: write", text)  # the eligible path of a mixed merge is still classified
        self.assertIn(T_SKILL, result["differing"])
        self.assertEqual((self.cursor(), self.state.applied()["by"]), (m2, "owner"))

    def test_preview_uses_the_same_assessment_as_apply(self):
        repo = Repo()
        L = repo.head
        m1 = repo.main({SKILL: ("100755", b"skill v0\n")}, "Merge pull request #1")
        self.setup(repo, L)
        _, out = self.adopt(m1)
        text = "\n".join(out)
        self.assertIn("refused: not a 100644 blob", text)
        self.assertNotIn(f"{T_SKILL}: write", text)

    def test_keeps_journal_entries_of_later_candidates(self):
        repo = Repo()
        L = repo.head
        m1 = repo.main({AGENT: b"agent v1\n"}, "Merge pull request #1")
        m2 = repo.main({SKILL: b"skill v1\n"}, "Merge pull request #2")
        self.setup(repo, L)
        self.state.save_journal([entry(m1, T_AGENT, "clean"), entry(m2, T_SKILL, "clean")])
        self.adopt(m1)
        self.assertEqual([e["merge"] for e in self.state.journal()], [m2])
        self.adopt(m2)
        self.assertEqual(self.state.journal(), [])

    def test_without_a_cursor_any_commit_on_the_chain(self):
        self.setup(cursor=False)
        self.adopt(self.L)
        self.assertEqual(self.cursor(), self.L)


# ---------------------------------------------------------------- mirror: fake git on PATH

DISPATCH = None


def setUpModule():
    # one executable every fake links to: macOS scans each new executable on its first run
    global DISPATCH
    DISPATCH = Path(tempfile.mkdtemp()) / "dispatch"
    DISPATCH.write_text('#!/bin/sh\n. "$0.body"\n')
    DISPATCH.chmod(0o755)


def tearDownModule():
    shutil.rmtree(DISPATCH.parent)


FAKE_GIT = r"""i=$(ls "{log}" | wc -l | tr -d ' ')
printf '%s\n' "$@" > "{log}/$i.argv"
env > "{log}/$i.env"
case " $* " in
  *" remote get-url origin "*) echo "{origin}" ;;
  *" clone "*) {clone} ;;
  *" fetch "*) {fetch} ;;
  *" rev-parse "*) echo {head} ;;
  *" rev-list "*) echo {head} ;;
esac
"""
SHELL_VARS = {"PWD", "SHLVL", "_", "OLDPWD"}


class Mirror(Base):
    HEAD = "f" * 40

    def git(self, clone='for a; do last=$a; done; mkdir -p "$last"', fetch=":", origin="git@github.com:o/r.git"):
        self.log = self.dir / "log"
        self.log.mkdir()
        bindir = self.dir / "bin"
        bindir.mkdir()
        path = bindir / "git"
        path.symlink_to(DISPATCH)
        Path(f"{path}.body").write_text(FAKE_GIT.format(log=self.log, origin=origin, clone=clone, fetch=fetch,
                                                        head=self.HEAD))
        hostile = {"GIT_DIR": "/nonexistent", "GIT_WORK_TREE": "/x", "GIT_CONFIG_COUNT": "1",
                   "GIT_CONFIG_KEY_0": "core.sshCommand", "GIT_CONFIG_VALUE_0": "evil", "GIT_ASKPASS": "/x",
                   "SSH_ASKPASS": "/x", "GIT_SSH_COMMAND": "evil", "GIT_CONFIG_PARAMETERS": "'a.b'='c'"}
        p = mock.patch.dict(os.environ, {**hostile, "PATH": f"{bindir}:{os.environ['PATH']}"})
        p.start()
        self.addCleanup(p.stop)

    def calls(self):
        out = []
        for argv in sorted(self.log.glob("*.argv"), key=lambda p: int(p.stem)):
            env = {}
            for line in Path(argv.with_suffix(".env")).read_text().splitlines():
                k, _, v = line.partition("=")
                if k not in SHELL_VARS:
                    env[k] = v
            out.append((argv.read_text().splitlines(), env))
        return out

    def checkout(self):
        repo = self.dir / "checkout"
        (repo / ".git").mkdir(parents=True)
        (repo / ".git/HEAD").write_text("ref: refs/heads/old\n")
        (repo / "dirty.txt").write_text("uncommitted\n")
        return repo

    def test_clone_and_fetch_argv_and_environment(self):
        self.git()
        repo = self.checkout()
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in repo.rglob("*") if p.is_file()}
        res = apply.run(self.home, repo)
        self.assertEqual(res["head"], self.HEAD)
        self.assertEqual(res["status"], "baseline-missing")
        calls = self.calls()
        self.assertGreaterEqual(len(calls), 4)
        url = "https://github.com/o/r.git"
        mirror = str(self.state.dir / "mirror.git")
        argvs = [a for a, _ in calls]
        self.assertEqual(argvs[0], ["-C", str(repo), "remote", "get-url", "origin"])
        clone = argvs[1]
        self.assertEqual(clone[:9], ["-c", "credential.helper=", "clone", "--bare", "--single-branch", "--branch",
                                     "main", "--no-tags", url])
        self.assertEqual(argvs[2], ["--git-dir", mirror, "-c", "credential.helper=", "fetch", "--no-tags", url,
                                    "+refs/heads/main:refs/heads/main"])
        for argv in argvs[1:]:
            self.assertNotIn(str(repo), " ".join(argv))  # only `remote get-url` reads the checkout
            self.assertTrue(argv[:2] == ["--git-dir", mirror] or "clone" in argv, argv)
        expected = {"PATH": os.environ["PATH"], "HOME": str(self.state.dir), "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}
        if os.environ.get("LANG"):
            expected["LANG"] = os.environ["LANG"]
        for argv, env in calls:
            with self.subTest(argv=argv[:3]):
                self.assertEqual({k: v for k, v in env.items() if not k.startswith("__CF")}, expected)
        self.assertTrue(Path(mirror).is_dir())
        self.assertEqual([p.name for p in self.state.dir.iterdir() if p.name.startswith(".mirror.")], [])
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in repo.rglob("*") if p.is_file()}, before)

    def test_existing_mirror_is_only_fetched(self):
        self.git()
        (self.state.dir / "mirror.git").mkdir(parents=True)
        apply.sync_mirror(self.state.dir, "https://github.com/o/r.git")
        self.assertNotIn("clone", [a for argv, _ in self.calls() for a in argv])

    def test_clone_timeout_kills_git_and_removes_the_temp_dir(self):
        pidfile = self.dir / "pid"
        self.git(clone=f'echo $$ > "{pidfile}"; exec sleep 30')
        with mock.patch.dict(apply.TIMEOUTS, {"clone": 1}), self.assertRaisesRegex(apply.ApplyError, "timed out"):
            apply.sync_mirror(self.state.dir, "https://github.com/o/r.git")
        pid = int(pidfile.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertEqual(sorted(p.name for p in self.state.dir.iterdir()), [])

    def test_a_timeout_kills_git_helpers_too(self):
        pidfile = self.dir / "helper.pid"
        self.git(clone=f'sleep 60 & echo $! > "{pidfile}"; wait')  # a helper like git-remote-https stalls

        def reap():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGKILL)
            except (OSError, ValueError):
                pass
        self.addCleanup(reap)
        with mock.patch.dict(apply.TIMEOUTS, {"clone": 1}), self.assertRaisesRegex(apply.ApplyError, "timed out"):
            apply.sync_mirror(self.state.dir, "https://github.com/o/r.git")
        helper = int(pidfile.read_text())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(helper, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        with self.assertRaises(ProcessLookupError):
            os.kill(helper, 0)

    def test_the_reader_walks_the_first_parent_chain(self):
        self.git()
        reader = apply.GitReader(self.dir / "m.git", "git", apply.git_env(self.state.dir), time.monotonic() + 30)
        self.assertEqual(reader.first_parents("HEADSHA"), [(self.HEAD, None)])
        [(argv, _)] = self.calls()
        self.assertEqual(argv, ["--git-dir", str(self.dir / "m.git"), "rev-list", "--first-parent", "--parents",
                                "HEADSHA"])

    def test_failed_clone_leaves_no_mirror(self):
        self.git(clone='for a; do last=$a; done; mkdir -p "$last"; exit 128')
        with self.assertRaisesRegex(apply.ApplyError, "exit 128"):
            apply.sync_mirror(self.state.dir, "https://github.com/o/r.git")
        self.assertEqual(sorted(p.name for p in self.state.dir.iterdir()), [])

    def test_fetch_failure_is_a_reported_error(self):
        self.git(fetch="echo 'could not resolve host' >&2; exit 128")
        repo = self.checkout()
        self.state.write("applied.json", {"commit": "a" * 40, "at": "t", "by": "owner", "run": None})
        res = apply.run(self.home, repo)
        self.assertEqual(res["status"], "error")
        self.assertIn("could not resolve host", res["decisions"][0])
        self.assertEqual(res["cursor"]["commit"], "a" * 40)

    def test_a_deadline_already_passed_runs_no_git(self):
        self.git()
        with self.assertRaisesRegex(apply.ApplyError, "no time left"):
            apply.sync_mirror(self.state.dir, "https://github.com/o/r.git", deadline=time.monotonic() - 1)
        self.assertEqual(self.calls(), [])

    def test_origin_forms(self):
        for origin, expected in (("git@github.com:o/r.git", "https://github.com/o/r.git"),
                                 ("https://github.com/o/r", "https://github.com/o/r.git"),
                                 ("ssh://git@github.com/o/r.git", "https://github.com/o/r.git")):
            with self.subTest(origin):
                shutil.rmtree(self.dir / "log", True)
                shutil.rmtree(self.dir / "bin", True)
                self.git(origin=origin)
                self.assertEqual(apply.public_url(self.checkout() if not (self.dir / "checkout").exists()
                                                  else self.dir / "checkout"), expected)
        shutil.rmtree(self.dir / "log", True)
        shutil.rmtree(self.dir / "bin", True)
        self.git(origin="https://gitlab.com/o/r.git")
        with self.assertRaisesRegex(apply.ApplyError, "not a GitHub"):
            apply.public_url(self.dir / "checkout")

    def test_an_unresolved_journal_is_reported_before_any_fetch(self):
        self.git(fetch="echo 'could not resolve host' >&2; exit 128")
        self.state.write("applied.json", {"commit": "a" * 40, "at": "t", "by": "owner", "run": None})
        self.state.save_journal([entry("b" * 40, T_AGENT, "unresolved", note="swapped back")])
        res = apply.run(self.home, self.checkout())
        self.assertEqual(res["status"], "blocked")
        self.assertEqual(self.calls(), [])
        [decision] = res["decisions"]
        self.assertIn(f"~/{T_AGENT}", decision)
        self.assertIn(str(self.state.dir / "backup/r"), decision)

    def check(self, repo):
        with mock.patch.object(apply, "sync_mirror", return_value=(repo, repo.head)), \
                mock.patch.object(apply, "public_url", return_value="u"), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = apply.main(["--check", "--home", str(self.home), "--repo", str(self.dir)])
        return code, out.getvalue()

    def check_offline(self):
        """--check against a fake git whose fetch fails: (exit code, stdout)."""
        self.git(fetch="echo 'could not resolve host' >&2; exit 128")
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            code = apply.main(["--check", "--home", str(self.home), "--repo", str(self.checkout())])
        return code, out.getvalue()

    def test_check_reports_an_unresolved_journal_before_any_fetch(self):
        self.state.write("applied.json", {"commit": "a" * 40, "at": "t", "by": "owner", "run": None})
        self.state.save_journal([entry("b" * 40, T_AGENT, "staged")])
        code, out = self.check_offline()
        self.assertEqual(code, 1)
        self.assertIn("status: blocked", out)
        self.assertIn(f"~/{T_AGENT}", out)
        self.assertEqual(self.calls(), [])

    def test_check_reports_invalid_state_before_any_fetch(self):
        self.state.dir.mkdir(parents=True)
        (self.state.dir / "applied.json").write_text('{"commit": "bad"}')
        code, out = self.check_offline()
        self.assertEqual(code, 2)
        self.assertIn("state invalid", out)
        self.assertEqual(self.calls(), [])

    def test_a_failed_preview_does_not_change_the_prediction(self):
        repo = Repo()
        L = repo.head
        m1 = repo.main({SKILL: b"skill v1\n"}, "Merge pull request #1")
        m2 = repo.main({SKILL: b"skill v2\n"}, "Merge pull request #2")
        real = repo.subject

        def subject(commit):
            if commit == m2:
                raise apply.ApplyError("git log: exit 128: object not found")
            return real(commit)
        repo.subject = subject
        make_home(repo, L, self.home)
        self.state.write("applied.json", {"commit": L, "at": "t", "by": "owner", "run": None})
        code, out = self.check(repo)
        self.assertEqual(code, 0)
        self.assertIn(f"{m1[:8]} #1 applicable", out)
        self.assertIn(f"preview stopped (not a prediction; the exit code ignores it): {m2[:8]}", out)

    def test_check_predicts_only_the_next_candidate(self):
        repo = Repo()
        L = repo.head
        m1 = repo.main({SKILL: b"skill v1\n"}, "Merge pull request #1")
        m2 = repo.main({SKILL: b"skill v2\n"}, "Merge pull request #2")
        make_home(repo, L, self.home)
        self.state.write("applied.json", {"commit": L, "at": "t", "by": "owner", "run": None})
        code, out = self.check(repo)
        self.assertEqual(code, 0)  # v0 -> v1 -> v2 applies cleanly; the second is not compared with a live at v1
        self.assertIn(f"{m1[:8]} #1 applicable", out)
        self.assertIn(f"{m2[:8]} #2 conflict", out)
        self.assertIn("(not a prediction)", out)
        self.assertNotIn("decision:", out)

    def test_the_cli_is_check_only(self):
        self.state.save_journal([entry("b" * 40, T_AGENT, "unresolved")])
        for argv in (["resolve", "--yes"], ["--check", "resolve", "--yes"], ["adopt", "b" * 40], []):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as stop:
                apply.main([*argv, "--home", str(self.home)])
            self.assertEqual(stop.exception.code, 2)
        self.assertEqual(len(self.state.journal()), 1)

    def test_check_cli_exit_codes(self):
        repo, L, M = scenario()
        make_home(repo, L, self.home)
        with mock.patch.object(apply, "sync_mirror", return_value=(repo, repo.head)), \
                mock.patch.object(apply, "public_url", return_value="u"), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = apply.main(["--check", "--home", str(self.home), "--repo", str(self.dir)])
        self.assertEqual(code, 1)  # no cursor: a decision proposes adopt
        self.assertIn("cursor: none", out.getvalue())
        self.assertIn(f"{M[:8]} #10 v1:", out.getvalue())
        self.assertFalse((self.state.dir / ".apply.lock").exists())


if __name__ == "__main__":
    unittest.main()
