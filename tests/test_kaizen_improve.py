"""Tests of scripts/kaizen/improve.py (the weekly stage). No real git, claude, gh, codex or ssh-keygen: every command is
tests/kaizen_fakes.py behind a link on PATH, and everything is written under the OS temp dir."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[1]
FAKES = Path(__file__).resolve().parent / "kaizen_fakes.py"
NOW = datetime(2026, 11, 19, 3, 0, tzinfo=timezone.utc)


def load(name):
    spec = importlib.util.spec_from_file_location(f"test_kaizen_{name}", REPO / f"scripts/kaizen/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


improve = load("improve")

SKILL = "home/dot_claude/skills/hiden/SKILL.md"
REF = "home/dot_claude/skills/hiden/references/a.md"
AGENT = "home/dot_claude/agents/w.md"
BASE_SHA = "1" * 40
BASE = {
    ".chezmoiroot": ("100644", "home\n"),
    ".chezmoi.toml.tmpl": ("100644", "[data]\n"),
    "home/.chezmoiignore": ("100644", "# local\n.config/age/**\n"),
    "home/.chezmoiremove": ("100644", ".tmux.conf\n"),
    SKILL: ("100644", "skill v0\n"),
    REF: ("100644", "ref v0\n"),
    AGENT: ("100644", "agent v0\n"),
    improve.HOOK: ("100755", (REPO / improve.HOOK).read_text()),
    improve.WRITING: ("100644", "WRITING-RULES-MARKER\n"),
    "AGENTS.md": ("100644", "agents\n"),
    "CLAUDE.md": ("120000", "AGENTS.md"),
    "scripts/kaizen/cycle.py": ("100755", "print(1)\n"),
}
PUBLIC = {"id": "pub1", "signal": "fix-pr", "where": "https://github.com/o/r/pull/7", "excerpt": "fix: the worker",
          "provenance": "public", "repo": "o/r", "ts": "2026-11-18T00:00:00Z"}
PRIVATE = [{"id": "PRIV-ID-1", "signal": "owner-reply", "where": "/x/PRIV-WHERE-1.jsonl:3",
            "excerpt": "PRIV-EXCERPT-1", "provenance": "owner", "repo": "PRIV-REPO-1", "ts": "PRIV-TS-1"},
           {"id": "PRIV-ID-2", "signal": "revert", "where": "https://github.com/o/secret/pull/1",
            "excerpt": "PRIV-EXCERPT-2", "provenance": "synthetic", "repo": "o/secret", "ts": "PRIV-TS-2"},
           {"id": "PRIV-ID-3", "signal": "ci-fail-main", "where": "o/r", "excerpt": "PRIV-EXCERPT-3",
            "provenance": "public", "repo": "o/r", "ts": "PRIV-TS-3"}]
MARKERS = ["PRIV-ID", "PRIV-WHERE", "PRIV-EXCERPT", "PRIV-REPO", "PRIV-TS", "secret/pull"]
READY = {"R3": {"status": "FAIL", "detail": ["OVER: x"], "owner": False}}
OUTPUT = {"change": True, "evidence_ids": ["pub1"], "summary": "s", "watch": "worker regression rate",
          "commit_message": "docs(hiden): tighten the skill", "pr_title": "docs(hiden): tighten the skill",
          "pr_body": "Tightens the skill."}
KEY_MARKER = "SIGNING-KEY-BYTES-MARKER"

DISPATCH = None


def setUpModule():
    global DISPATCH
    DISPATCH = Path(tempfile.mkdtemp()) / "dispatch"
    DISPATCH.write_text('#!/bin/sh\n. "$0.body"\n')
    DISPATCH.chmod(0o755)


def tearDownModule():
    shutil.rmtree(DISPATCH.parent)


def pr(sha, ref="kaizen/x", repo="o/r", base="main", number=9, state="open"):
    return {"number": number, "html_url": f"https://github.com/o/r/pull/{number}", "state": state,
            "head": {"ref": ref, "sha": sha, "repo": {"full_name": repo}}, "base": {"ref": base},
            "created_at": "2026-11-18T00:00:00Z"}


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class Fakes(unittest.TestCase):
    """A temp home, checkout and K with every command faked."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.fdir, self.bin = self.dir / "fake", self.dir / "bin"
        self.fdir.mkdir()
        self.bin.mkdir()
        for tool in ("git", "claude", "gh", "codex", "ssh-keygen"):
            path = self.bin / tool
            path.symlink_to(DISPATCH)
            Path(f"{path}.body").write_text(f'exec "{sys.executable}" "{FAKES}" {tool} "{self.fdir}" "$@"\n')
        check = self.dir / "public-check.py"
        check.write_text(f"import runpy, sys\nsys.argv = [{str(FAKES)!r}, 'public-check', {str(self.fdir)!r}, "
                         f"*sys.argv[1:]]\nrunpy.run_path({str(FAKES)!r}, run_name='__main__')\n")
        self.home = self.dir / "home"
        self.k = self.home / ".claude/kaizen"
        self.k.mkdir(parents=True)
        (self.k / "improve-enabled").touch()
        (self.k / "private-terms").write_text("zebra\n")
        self.repo = self.dir / "checkout"
        self.repo.mkdir()
        (self.repo / "host.toml").write_text('hostName = "alice-mbp"\n')
        (self.home / ".ssh").mkdir()
        self.key = self.home / ".ssh/id_kaizen_marker"
        self.key.write_text(KEY_MARKER)
        Path(f"{self.key}.pub").write_text("ssh-ed25519 AAAA\n")
        (self.home / ".config/git").mkdir(parents=True)
        (self.home / ".config/git/config.local").write_text(
            "[user]\n\tname = A Person\n\temail = a@example.com\n\tsigningkey = ~/.ssh/id_kaizen_marker.pub\n")
        (self.home / ".claude/attention").mkdir(parents=True)
        (self.home / ".claude/attention/budget.json").write_text(json.dumps(
            {"caps": {}, "registers": [], "prose": {f"~/.claude/{SKILL[len('home/dot_claude/'):]}": 100}}))
        blobs, tree = {}, {}
        for path, (mode, text) in BASE.items():
            data = text.encode()
            o = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
            blobs[o], tree[path] = data.hex(), [mode, o]
        self.db({"blobs": blobs, "commits": {BASE_SHA: {"tree": tree, "parents": [], "message": "base\n"}},
                 "refs": {"refs/heads/main": BASE_SHA}, "server": {}})
        self.scenario()
        for p in (mock.patch.dict(os.environ, {"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": str(self.home)}),
                  mock.patch.object(improve, "PUBLIC_CHECK", check)):
            p.start()
            self.addCleanup(p.stop)

    # -- helpers
    def db(self, value=None):
        if value is not None:
            (self.fdir / "db.json").write_text(json.dumps(value))
        return json.loads((self.fdir / "db.json").read_text())

    def scenario(self, **changes):
        base = {"claude": {"edits": {SKILL: "skill v1\n"}, "result": {"structured_output": OUTPUT}},
                "open": [[]], "lookup": "auto", "create": {"stdout": "https://github.com/o/r/pull/9\n"},
                "codex": {"verdict": {"high": []}}, "public_check": {"code": 0}, "markers": MARKERS + [KEY_MARKER]}
        current = json.loads((self.fdir / "scenario.json").read_text()) if changes.pop("keep", False) else base
        current.update(changes)
        (self.fdir / "scenario.json").write_text(json.dumps(current))
        (self.fdir / "calls.json").unlink(missing_ok=True)

    def weekly(self, items=None, now=NOW, seconds=60, slug="o/r", gh_source="ok"):
        return improve.weekly(self.k, self.home, self.repo, slug, [PUBLIC, *PRIVATE] if items is None else items,
                              READY, now, time.monotonic() + seconds, sources={"gh": {"status": gh_source}})

    def calls(self, tool=None):
        try:
            lines = (self.fdir / "log.jsonl").read_text().splitlines()
        except FileNotFoundError:
            return []
        return [c for c in map(json.loads, lines) if tool is None or c["tool"] == tool]

    def git_calls(self, cmd):
        return [c for c in self.calls("git") if cmd in c["argv"]]

    def attempts(self):
        d = self.k / improve.PROPOSALS
        return sorted(p.name for p in d.iterdir() if improve.ATTEMPT.fullmatch(p.name)) if d.exists() else []

    def result(self, name=None):
        name = name or self.attempts()[-1]
        return json.loads((self.k / improve.PROPOSALS / name / "result.json").read_text())

    def writes(self):
        """Remote writes the fakes saw: pushes and PR creations."""
        return self.git_calls("push") + [c for c in self.calls("gh") if c["argv"][:2] == ["pr", "create"]]

    def jsonl(self, name):
        try:
            return [json.loads(l) for l in (self.fdir / name).read_text().splitlines()]
        except FileNotFoundError:
            return []

    def old_attempt(self, days=10, **fields):
        a = improve.Attempt.create(self.k, NOW - timedelta(days=days), {"lane": "model", "cost_usd": "unknown",
                                                                         "base": BASE_SHA, **fields})
        return a

    def publishing(self, **remote):
        """An attempt left publishing after its push, with frozen title and body, and the server ref at its oid."""
        a = self.old_attempt(outcome="publishing")
        (self.home / improve.STATE / "mirror.git").mkdir(parents=True, exist_ok=True)  # the run that pushed made it
        a.write("title.txt", "docs: t")
        a.write("body.md", "Body.\n")
        branch = f"kaizen/improve-{a.data['id']}"
        a.update(branch=branch, frozen={"title": hashlib.sha256(b"docs: t").hexdigest(),
                                        "body": hashlib.sha256(b"Body.\n").hexdigest()})
        r = {"repo": "o/r", "ref": f"refs/heads/{branch}", "branch": branch, "oid": "c" * 40,
             "push_dispatched": True, "pr_dispatched": True, **remote}
        a.remote(**r)
        db = self.db()
        db["server"][r["ref"]] = "c" * 40
        self.db(db)
        return a, r

    def assertNoWrites(self):
        self.assertEqual(self.writes(), [])


class Weekly(Fakes):
    # ---------------------------------------------------------------- C1, C2: enablement and the lock
    def test_c1_off_unless_a_regular_file(self):
        target = self.dir / "elsewhere"
        target.touch()
        for setup in ("missing", "symlink", "directory"):
            with self.subTest(setup):
                enable = self.k / "improve-enabled"
                if enable.is_dir() and not enable.is_symlink():
                    enable.rmdir()
                else:
                    enable.unlink(missing_ok=True)
                if setup == "symlink":
                    enable.symlink_to(target)
                elif setup == "directory":
                    enable.mkdir()
                res = self.weekly()
                self.assertEqual((res["enabled"], res["status"], res["attempt"]), (False, "off", None))
                self.assertEqual(self.calls(), [])
                self.assertFalse((self.k / improve.PROPOSALS).exists())
                self.assertFalse((self.k / improve.LOCK).exists())

    def test_c2_a_held_lock_skips_without_any_call(self):
        with open(self.k / improve.LOCK, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            res = self.weekly()
        self.assertEqual(res["status"], "skipped:locked")
        self.assertEqual((self.calls(), self.attempts()), ([], []))

    def test_c2_two_ordered_runs_one_attempt(self):
        started = self.fdir / "claude.pid"
        self.scenario(claude={"edits": {SKILL: "skill v1\n"}, "result": {"structured_output": OUTPUT}, "sleep": 2,
                              "pidfile": str(started)})
        first = {}
        t = threading.Thread(target=lambda: first.update(self.weekly()))
        t.start()
        deadline = time.monotonic() + 30
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(started.exists())
        before = len(self.calls())
        second = self.weekly()
        self.assertEqual(second["status"], "skipped:locked")
        self.assertEqual(len(self.calls()), before)  # the second run made no call, recovery included
        t.join(60)
        self.assertEqual(first["status"], "attempted")
        self.assertEqual(len(self.attempts()), 1)
        self.assertTrue(self.result()["outcome"].startswith("pr "))

    # ---------------------------------------------------------------- C3, C4: gates
    def test_c3_an_attempt_within_7_days_blocks(self):
        self.old_attempt(days=3, outcome="no-change")
        res = self.weekly()
        self.assertEqual(res["status"], "skipped:not due")
        self.assertEqual((self.calls("gh"), self.calls("claude"), len(self.attempts())), ([], [], 1))

    def test_c3_an_uncleared_remote_unknown_blocks_until_clear(self):
        a = self.old_attempt(days=10, outcome=improve.REMOTE_UNKNOWN, reason="ref missing",
                             remote={"branch": "kaizen/improve-x"})
        res = self.weekly()
        self.assertEqual(res["status"], "skipped:remote-unknown")
        self.assertEqual(self.calls(), [])
        self.assertTrue(any("cycle.py clear" in d and "kaizen/improve-x" in d for d in res["decisions"]))
        self.assertEqual(improve.clear(self.k, a.data["id"])["cleared"], a.data["id"])
        res = self.weekly()
        self.assertEqual(res["status"], "attempted")
        self.assertNotEqual(self.calls("claude"), [])

    def test_c3_clear_only_lifts_remote_unknown_and_takes_the_lock(self):
        a = self.old_attempt(days=10, outcome="no-change")
        with self.assertRaises(SystemExit):
            improve.clear(self.k, a.data["id"])
        b = self.old_attempt(days=9, outcome=improve.REMOTE_UNKNOWN)
        with open(self.k / improve.LOCK, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.assertRaisesRegex(SystemExit, "running"):
                improve.clear(self.k, b.data["id"])
        self.assertNotIn("cleared", self.result(b.data["id"]))

    def test_c4_open_kaizen_pr_on_a_later_page_blocks(self):
        self.scenario(open=[[[pr("a", ref="feature/x")], [pr("b", ref="kaizen/y")]]])
        res = self.weekly()
        self.assertEqual(res["status"], "skipped:open kaizen PR #9")
        [call] = self.calls("gh")
        self.assertEqual(call["argv"][:4], ["api", "--paginate", "--slurp", "repos/o/r/pulls?state=open&per_page=100"])
        self.assertEqual((self.calls("claude"), self.attempts()), ([], []))

    def test_c4_a_fork_head_does_not_count_and_gh_failure_skips(self):
        self.scenario(open=[[[pr("a", ref="kaizen/y", repo="someone/r")]]])
        self.assertEqual(self.weekly()["status"], "attempted")
        shutil.rmtree(self.k / improve.PROPOSALS)
        self.scenario(open=["fail"])
        res = self.weekly()
        self.assertTrue(res["status"].startswith("skipped:gh"), res["status"])
        self.assertEqual(self.attempts(), [])

    # ---------------------------------------------------------------- C5, C6: lanes and preflight
    def test_c5_an_unread_github_source_is_not_absence(self):
        for status in ("fail", "off"):
            with self.subTest(status):
                res = self.weekly(items=PRIVATE, gh_source=status)
                self.assertEqual(res["status"], f"skipped:GitHub observation {status}")
                self.assertEqual(self.attempts(), [])
                self.assertEqual(self.calls("claude"), [])

    def test_c5_without_public_evidence_no_model_and_a_proposal(self):
        res = self.weekly(items=PRIVATE)
        self.assertEqual(self.result()["outcome"], "proposal:no-public-evidence")
        self.assertEqual(res["cost_usd"], 0)
        proposal = (self.k / improve.PROPOSALS / self.attempts()[0] / "proposal.md").read_text()
        self.assertIn("PRIV-EXCERPT-1", proposal)
        self.assertIn("OVER: x", proposal)
        self.assertEqual((self.calls("claude"), self.calls("codex")), ([], []))
        self.assertEqual([c["argv"][0] for c in self.calls("gh")], ["api"])
        self.assertNoWrites()

    def test_c6_a_missing_host_toml_or_a_broken_terms_file_skips(self):
        (self.repo / "host.toml").unlink()
        res = self.weekly()
        self.assertEqual(res["status"], "skipped:host.toml unreadable")
        (self.repo / "host.toml").write_text('hostName = "alice-mbp"\n')
        (self.k / "private-terms").unlink()
        (self.k / "private-terms").mkdir()  # present but not a readable file: fail closed
        res = self.weekly()
        self.assertEqual(res["status"], "skipped:private-terms unreadable")
        self.assertEqual((self.calls("claude"), self.attempts()), ([], []))

    def test_c6_private_terms_are_optional(self):
        (self.k / "private-terms").unlink()
        self.weekly()
        self.assertTrue(self.result()["outcome"].startswith("pr "), self.result())
        [checked] = self.jsonl("checked.jsonl")
        self.assertEqual(checked["argv"][checked["argv"].index("--private-terms") + 1], os.devnull)

    def test_c6_unusable_key_or_claude_auth_skips(self):
        for change, needle in (({"keygen_code": 1}, "signing key"), ({"auth_code": 1}, "claude auth")):
            with self.subTest(needle):
                self.scenario(**change)
                res = self.weekly()
                self.assertIn(needle, res["status"])
                self.assertEqual([c for c in self.calls("claude") if c["argv"][:1] == ["-p"]], [])
                self.assertEqual(self.attempts(), [])

    def test_claude_gets_the_owners_endpoint_and_nothing_else_from_settings(self):
        settings = self.home / ".claude/settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        cases = {"proxy": ({"env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8317", "ANTHROPIC_AUTH_TOKEN": "tok-x",
                                    "OTHER": "y"}}, {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8317",
                                                     "ANTHROPIC_AUTH_TOKEN": "tok-x"}),
                 "no proxy": ({"env": {}}, {}),
                 "no file": (None, {})}
        for name, (content, expected) in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                (self.fdir / "log.jsonl").unlink(missing_ok=True)
                if content is None:
                    settings.unlink(missing_ok=True)
                else:
                    settings.write_text(json.dumps(content))
                self.weekly()
                [call] = [c for c in self.calls("claude") if c["argv"][:1] == ["-p"]]
                self.assertEqual({k: v for k, v in call["env"].items() if k.startswith("ANTHROPIC")}, expected)
                self.assertNotIn("OTHER", call["env"])
                self.assertNotIn("tok-x", json.dumps(call["argv"]) + call.get("stdin", ""))

    def endpoint(self, env):
        settings = self.home / ".claude/settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps({"env": env}) if not isinstance(env, str) else env)

    def test_the_endpoint_credential_never_reaches_a_commit_or_a_record(self):
        self.endpoint({"ANTHROPIC_BASE_URL": "http://127.0.0.1:8317", "ANTHROPIC_AUTH_TOKEN": "tok-canary-123"})
        self.scenario(claude={"edits": {SKILL: "skill tok-canary-123\n"}, "result": {"structured_output": OUTPUT}})
        self.weekly()
        r = self.result()
        self.assertEqual(r["outcome"], "proposal:credential")
        self.assertNoWrites()
        self.assertEqual(self.git_calls("commit-tree"), [])
        saved = "".join(p.read_text() for p in (self.k / improve.PROPOSALS / r["id"]).iterdir())
        self.assertNotIn("tok-canary-123", saved)
        self.assertIn("<redacted>", saved)

    def test_an_echoed_credential_in_an_error_is_redacted(self):
        self.endpoint({"ANTHROPIC_AUTH_TOKEN": "tok-canary-123"})
        echo = {"result": "bad request: Bearer tok-canary-123", "total_cost_usd": 0, "is_error": True}
        self.scenario(claude={"result": echo, "code": 1, "stderr": "auth: Bearer tok-canary-123\n"})
        res = self.weekly()
        self.assertEqual(self.result()["outcome"], improve.UNAVAILABLE)
        self.assertNotIn("tok-canary-123", json.dumps(self.result()) + json.dumps(res))

    def test_malformed_endpoint_settings_fall_back_to_the_default_login(self):
        for name, env in {"array": ["x"], "string": "x", "true": True, "nul": {"ANTHROPIC_AUTH_TOKEN": "a\0b"},
                          "surrogate": {"ANTHROPIC_AUTH_TOKEN": "a\ud800b"}, "not json": "{"}.items():
            with self.subTest(name):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                (self.fdir / "log.jsonl").unlink(missing_ok=True)
                if name == "not json":
                    self.endpoint("{")
                else:
                    self.endpoint(env)
                self.weekly()
                [call] = [c for c in self.calls("claude") if c["argv"][:1] == ["-p"]]
                self.assertFalse([k for k in call["env"] if k.startswith("ANTHROPIC")])

    def test_only_claude_gets_the_endpoint(self):
        self.endpoint({"ANTHROPIC_AUTH_TOKEN": "tok-canary-123"})
        self.weekly()
        for c in self.calls():
            if c["tool"] != "claude":
                self.assertNotIn("tok-canary-123", json.dumps(c.get("env", {})), c["tool"])

    # ---------------------------------------------------------------- C7, C8, C17: what claude gets
    def test_c7_c8_c17_claude_inputs(self):
        self.weekly()
        [call] = [c for c in self.calls("claude") if c["argv"][:1] == ["-p"]]
        argv = call["argv"]
        flags = {"--tools": "Read,Edit,Write,Grep,Glob", "--permission-mode": "acceptEdits",
                 "--permission-prompts": "none", "--output-format": "json", "--model": "claude-opus-5-5",
                 "--effort": "xhigh", "--max-budget-usd": "50"}
        for flag, value in flags.items():
            self.assertEqual(argv[argv.index(flag) + 1], value, flag)
        for flag in ("-p", "--safe-mode", "--restricted", "--strict-mcp-config", "--no-session-persistence"):
            self.assertIn(flag, argv)
        self.assertEqual(json.loads(argv[argv.index("--json-schema") + 1]), improve.SCHEMA)
        self.assertLessEqual(set(call["env"]) - {"__CF_USER_TEXT_ENCODING", "PWD", "SHLVL", "_", "OLDPWD"},
                             set(improve.CLAUDE_ENV) | set(improve.ENDPOINT_ENV))
        self.assertEqual(call["env"]["HOME"], str(self.home))
        state = self.home / improve.STATE
        self.assertEqual(Path(call["cwd"]).parent.resolve(), state.resolve())
        self.assertTrue(Path(call["cwd"]).name.startswith("tree-"))
        self.assertEqual(call["pgid"], call["pid"])
        self.assertNotEqual(call["pgid"], os.getpgid(0))
        prompt = call["stdin"]
        self.assertIn("pub1", prompt)
        self.assertIn("WRITING-RULES-MARKER", prompt)  # writing.md from the base commit
        everything = json.dumps(call) + (self.k / improve.PROPOSALS / self.attempts()[0] / "brief.md").read_text()
        for marker in MARKERS + [KEY_MARKER, self.key.name, "signingkey", "gpg"]:
            self.assertNotIn(marker, everything)
        self.assertEqual(json.loads((self.fdir / "scan.json").read_text()), [])  # nor in the tree claude saw
        self.assertFalse(any(state.glob("tree-*")))  # the tree is removed

    def test_c17_the_pushed_oid_is_the_checked_signed_commit(self):
        self.weekly()
        r = self.result()
        oid = r["oid"]
        commit = self.db()["commits"][oid]
        self.assertTrue(commit["signed"])
        self.assertEqual(commit["config"]["gpg.format"], "ssh")
        self.assertEqual(commit["config"]["user.signingkey"], str(self.key))
        self.assertEqual(commit["env"].get("GIT_NO_REPLACE_OBJECTS"), "1")
        [checked] = self.jsonl("checked.jsonl")
        self.assertEqual(checked["argv"][0], f"{BASE_SHA}..{oid}")
        [push] = self.git_calls("push")
        self.assertEqual(push["argv"][-1], f"{oid}:refs/heads/{r['branch']}")
        self.assertEqual(r["remote"]["oid"], oid)
        self.assertEqual(self.db()["server"][f"refs/heads/{r['branch']}"], oid)

    # ---------------------------------------------------------------- C9, C10: the result
    def test_c9_cost_recorded_only_when_finite(self):
        cases = {"number": ({"total_cost_usd": 3.5}, 3.5), "missing": ({"total_cost_usd": None}, "unknown"),
                 "nan": (None, "unknown"), "bool": ({"total_cost_usd": True}, "unknown")}
        outcomes = set()
        for name, (extra, expected) in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                db = self.db()
                db["server"] = {}
                self.db(db)
                result = {"type": "result", "subtype": "success", "is_error": False, "structured_output": OUTPUT}
                spec = ({"raw": json.dumps(result)[:-1] + ', "total_cost_usd": NaN}'} if extra is None
                        else {"result": {**result, **extra}})
                if extra and extra.get("total_cost_usd") is None:
                    spec = {"raw": json.dumps(result)}
                self.scenario(claude={"edits": {SKILL: "skill v1\n"}, **spec})
                res = self.weekly()
                self.assertEqual((self.result()["cost_usd"], res["cost_usd"]), (expected, expected))
                outcomes.add(self.result()["outcome"].split()[0])
        self.assertEqual(outcomes, {"pr"})  # the cost never changes the outcome

    def test_c9_no_result_is_unknown_and_failed(self):
        self.scenario(claude={"raw": "", "code": 1})
        res = self.weekly()
        self.assertEqual((self.result()["outcome"], self.result()["cost_usd"], res["cost_usd"]),
                         ("failed:model-result", "unknown", "unknown"))

    def test_c10_a_nonzero_exit_rejects_a_success_shaped_result(self):
        self.scenario(claude={"edits": {SKILL: "skill v1\n"}, "result": {"structured_output": OUTPUT,
                                                                       "total_cost_usd": 2.0}, "code": 17})
        self.weekly()
        r = self.result()
        self.assertEqual((r["outcome"], r["cost_usd"]), ("failed:model-result", 2.0))
        self.assertNoWrites()
        self.assertIn("skill v1", (self.k / improve.PROPOSALS / r["id"] / "diff.patch").read_text())

    def test_c3_a_model_that_did_no_work_does_not_use_up_the_week(self):
        limit = {"result": "You've hit your weekly limit", "total_cost_usd": 0, "is_error": True}
        self.scenario(claude={"result": limit, "code": 1})
        self.weekly()
        self.assertEqual(self.result()["outcome"], improve.UNAVAILABLE)
        self.scenario(claude={"edits": {SKILL: "skill v1\n"}, "result": {"structured_output": OUTPUT}})
        self.weekly()  # the next day: a new attempt, not "not due"
        outcomes = sorted(self.result(i)["outcome"] for i in self.attempts())
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(outcomes[0], improve.UNAVAILABLE)
        self.assertTrue(outcomes[1].startswith("pr "), outcomes)

    def test_c3_zero_cost_with_tokens_still_uses_up_the_week(self):
        worked = {"result": "error", "total_cost_usd": 0, "is_error": True, "usage": {"output_tokens": 12}}
        self.scenario(claude={"edits": {SKILL: "skill v1\n"}, "result": worked, "code": 1})
        self.weekly()
        self.assertEqual(self.result()["outcome"], "failed:model-result")
        self.weekly()
        self.assertEqual(len(self.attempts()), 1)  # not due

    def test_c3_malformed_token_counts_are_work(self):
        odd = {"result": "x", "total_cost_usd": 0, "is_error": True, "usage": {"output_tokens": "12"}}
        self.scenario(claude={"result": odd, "code": 1})
        self.weekly()
        self.assertEqual(self.result()["outcome"], "failed:model-result")

    def test_c18_an_unfinished_publication_is_recovered_behind_a_newer_attempt(self):
        a, r = self.publishing()
        later = self.k / improve.PROPOSALS / (a.dir.name[:9] + "ffffff")
        if later == a.dir:
            later = self.k / improve.PROPOSALS / (a.dir.name[:9] + "fffffe")
        shutil.copytree(a.dir, later)
        data = json.loads((later / "result.json").read_text())
        data.update(outcome=improve.UNAVAILABLE, id=later.name)
        data.pop("remote", None)
        (later / "result.json").write_text(json.dumps(data))
        self.scenario(open=["fail"])
        self.weekly()
        self.assertEqual(self.result(a.dir.name)["outcome"], "pr https://github.com/o/r/pull/9")

    def test_c3_an_unavailable_attempt_does_not_hide_a_counting_one(self):
        self.scenario(claude={"result": {"result": "x", "total_cost_usd": 2.0, "is_error": True}, "code": 1})
        self.weekly()
        counting = self.attempts()[0]
        later = self.k / improve.PROPOSALS / (counting[:9] + "ffffff")  # same start, a name that sorts after
        shutil.copytree(self.k / improve.PROPOSALS / counting, later)
        data = json.loads((later / "result.json").read_text())
        data.update(outcome=improve.UNAVAILABLE, id=later.name)
        (later / "result.json").write_text(json.dumps(data))
        self.weekly()
        self.assertEqual(len(self.attempts()), 2)  # still not due: the $2 attempt counts

    def test_c9_a_cost_too_large_for_a_float_is_unknown(self):
        result = {"type": "result", "subtype": "success", "is_error": False, "structured_output": OUTPUT}
        self.scenario(claude={"edits": {SKILL: "skill v1\n"},
                              "raw": json.dumps(result)[:-1] + ', "total_cost_usd": 1' + "0" * 309 + "}"})
        res = self.weekly()
        self.assertEqual((self.result()["cost_usd"], res["cost_usd"]), ("unknown", "unknown"))
        self.assertTrue(self.result()["outcome"].startswith("pr "))

    def test_c10_invalid_results_end_without_a_pr(self):
        bad = {"error subtype": {"subtype": "error_max_budget_usd", "structured_output": OUTPUT},
               "is_error": {"is_error": True, "structured_output": OUTPUT},
               "schema": {"structured_output": {**OUTPUT, "watch": 3}},
               "extra key": {"structured_output": {**OUTPUT, "more": "x"}},
               "empty ids": {"structured_output": {**OUTPUT, "evidence_ids": []}},
               "foreign id": {"structured_output": {**OUTPUT, "evidence_ids": ["pub1", "PRIV-ID-1"]}},
               "no change": {"structured_output": {**OUTPUT, "change": False}}}
        expected = {"empty ids": "proposal:evidence-ids", "foreign id": "proposal:evidence-ids",
                    "no change": "no-change"}
        for name, result in bad.items():
            with self.subTest(name):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                self.scenario(claude={"edits": {SKILL: "skill v1\n"}, "result": result})
                self.weekly()
                self.assertEqual(self.result()["outcome"], expected.get(name, "failed:model-result"))
                self.assertNoWrites()
                self.assertEqual(self.calls("codex"), [])

    # ---------------------------------------------------------------- C11: the stage deadline
    def test_c11_deadline_kills_claude_and_its_grandchild(self):
        grandchild = self.fdir / "grandchild.pid"
        self.scenario(claude={"sleep": 60, "grandchild": str(grandchild)})
        started = time.monotonic()
        self.weekly(seconds=4)
        self.assertLess(time.monotonic() - started, 30)
        self.assertEqual(self.result()["outcome"], "failed:timeout")
        pid = int(grandchild.read_text())
        self.addCleanup(lambda: alive(pid) and os.kill(pid, signal.SIGKILL))
        for _ in range(100):
            if not alive(pid):
                break
            time.sleep(0.05)
        self.assertFalse(alive(pid))
        self.assertNoWrites()

    def test_c11_deadline_in_recovery_keeps_publishing(self):
        a, r = self.publishing()
        self.scenario(lookup=[{"sleep": 30}])
        res = self.weekly(seconds=3)
        self.assertEqual(res["status"], "skipped:deadline in recovery")
        after = self.result(a.data["id"])
        self.assertEqual((after["outcome"], after["remote"]), ("publishing", r))
        self.assertNoWrites()

    # ---------------------------------------------------------------- C12, C13: what may be published
    def test_c12_anything_but_plain_modifications_is_a_proposal(self):
        cases = {"new file": {"create": ["home/dot_claude/skills/hiden/references/new.md"]},
                 "outside v1": {"edits": {"home/.chezmoiignore": "# changed\n"}},
                 "repo-only path": {"edits": {SKILL: "skill v1\n", "AGENTS.md": "changed\n"}},
                 "through the symlink": {"edits": {"CLAUDE.md": "changed\n"}},
                 "made executable": {"edits": {SKILL: "skill v1\n"}, "chmod": [SKILL]},
                 "whitespace only": {"edits": {SKILL: "  \n"}},
                 "executable edited": {"edits": {"scripts/kaizen/cycle.py": "print(2)\n"}}}
        for name, spec in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                self.scenario(claude={"result": {"structured_output": OUTPUT}, **spec})
                self.weekly()
                self.assertTrue(self.result()["outcome"].startswith("proposal:"), self.result())
                self.assertNoWrites()

    def test_c13_prose_caps_by_the_hook_rules(self):
        cases = {"over the cap in UTF-8 bytes": {SKILL: "あ" * 40 + "\n"},  # 40 characters, 121 bytes
                 "a capped dir without an entry": {REF: "ref v1\n"}}
        for name, edits in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                self.scenario(claude={"edits": edits, "result": {"structured_output": OUTPUT}})
                self.weekly()
                self.assertEqual(self.result()["outcome"], "proposal:caps", self.result().get("reason"))
                self.assertNoWrites()
        shutil.rmtree(self.k / improve.PROPOSALS)
        self.scenario(claude={"edits": {AGENT: "agent v1\n"}, "result": {"structured_output": OUTPUT}})
        self.weekly()
        self.assertTrue(self.result()["outcome"].startswith("pr "))  # agents/ is not a capped dir

    # ---------------------------------------------------------------- C14, C15: Codex and public-check
    def test_c14_codex_runs_read_only_after_the_freeze(self):
        self.weekly()
        order = [c["tool"] if c["tool"] == "codex" else c["argv"][1] for c in self.calls()
                 if c["tool"] == "codex" or c["argv"][:2] == ["pr", "create"]]
        self.assertEqual(order, ["codex", "create"])  # codex, then gh pr create
        [call] = self.calls("codex")
        self.assertEqual(call["argv"][call["argv"].index("-s") + 1], "read-only")
        self.assertIn("approval_policy=never", call["argv"])
        self.assertEqual(len(self.jsonl("checked.jsonl")), 1)  # public-check ran before it
        self.assertEqual(self.result()["codex_runs"], 1)

    def test_c14_any_codex_failure_is_a_proposal(self):
        cases = {"exit": {"code": 1, "verdict": {"high": []}}, "missing": {}, "invalid": {"verdict": "not json"},
                 "wrong shape": {"verdict": {"high": "x"}}, "high": {"verdict": {"high": ["loosens a guard"]}},
                 "own timeout": {"sleep": 10}}
        for name, spec in cases.items():
            with self.subTest(name), mock.patch.dict(improve.SECONDS, {"codex": 1}):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                self.scenario(codex=spec)
                self.weekly()
                self.assertTrue(self.result()["outcome"].startswith("proposal:codex"), self.result())
                self.assertNoWrites()

    def test_c14_the_stage_deadline_during_codex_fails_before_any_push(self):
        self.scenario(codex={"sleep": 60})
        with mock.patch.dict(improve.SECONDS, {"codex": 600}):
            self.weekly(seconds=6)
        self.assertEqual(self.result()["outcome"], "failed:timeout")
        self.assertNotIn("remote", self.result())
        self.assertNoWrites()

    def test_c15_public_check_inputs_are_what_is_published(self):
        self.weekly()
        r = self.result()
        [checked] = self.jsonl("checked.jsonl")
        argv = checked["argv"]
        opt = lambda flag: argv[argv.index(flag) + 1]
        self.assertEqual(opt("--host-toml"), str(self.repo / "host.toml"))
        self.assertEqual(opt("--private-terms"), str(self.k / "private-terms"))
        self.assertEqual(Path(checked["cwd"]).resolve(), (self.home / improve.STATE / "mirror.git").resolve())
        self.assertEqual(checked["env"].get("GIT_CONFIG_GLOBAL"), os.devnull)
        [created] = self.jsonl("created.jsonl")
        cargv = created["argv"]
        copt = lambda flag: cargv[cargv.index(flag) + 1]
        self.assertEqual(copt("--title"), opt("--title"))
        self.assertEqual(created["body"], checked["body"])
        self.assertEqual(copt("--head"), opt("--branch"))
        [push] = self.git_calls("push")
        self.assertEqual(push["argv"][-1].split(":")[1], f"refs/heads/{opt('--branch')}")
        self.assertIn("https://github.com/o/r/pull/7", bytes.fromhex(created["body"]).decode())
        self.assertEqual((copt("--repo"), copt("--base")), ("o/r", "main"))
        self.assertEqual(r["outcome"], "pr https://github.com/o/r/pull/9")

    def test_c15_more_than_one_commit_is_a_proposal(self):
        self.scenario(rev_list_count=2)
        self.weekly()
        self.assertEqual(self.result()["outcome"], "proposal:check")
        self.assertEqual(self.jsonl("checked.jsonl"), [])
        self.assertNoWrites()

    def test_c15_an_added_broken_relative_link_is_a_proposal(self):
        cases = {"broken": ("skill v1 see [ref](references/missing.md)\n", "proposal:links"),
                 "resolves": ("skill v1 see [ref](references/a.md#top) and [dir](references/)\n", "pr "),
                 "a URL": ("skill v1 see [x](https://example.com/a)\n", "pr "),
                 "inline code": ("skill v1 `[x](references/none.md)`\n", "pr "),
                 "fenced code": ("skill v1\n```\n[x](references/none.md)\n```\n", "pr "),
                 "angle brackets": ("skill v1 [a](<references/a.md>)\n", "pr "),
                 "broken reference": ("skill v1 [x][r]\n\n[r]: references/none.md\n", "proposal:links"),
                 "backticks in other blocks": ("skill v1 `\n\n[x](references/none.md)\n\n`\n", "proposal:links"),
                 "info string is no closer": ("skill v1\n```md\n```yaml\n[x](references/none.md)\n```\n", "pr ")}
        for name, (text, outcome) in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                db = self.db()
                db["server"], db["prs"] = {}, []
                self.db(db)
                self.scenario(claude={"edits": {SKILL: text}, "result": {"structured_output": OUTPUT}})
                self.weekly()
                self.assertTrue(self.result()["outcome"].startswith(outcome), self.result())

    def test_m6_mode_and_link_changes_are_named_in_the_diff(self):
        cases = {"mode only": ({"chmod": [SKILL]}, f"# {SKILL}: mode 100644 -> mode 100755"),
                 "link retarget": ({"symlink": {"CLAUDE.md": "README.md"}},
                                   "# CLAUDE.md: link to AGENTS.md -> link to README.md")}
        for name, (spec, needle) in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                self.scenario(claude={"result": {"structured_output": OUTPUT}, **spec})
                self.weekly()
                self.assertEqual(self.result()["outcome"], "proposal:tree")
                self.assertIn(needle, (self.k / improve.PROPOSALS / self.attempts()[0] / "diff.patch").read_text())

    def test_m6_a_refused_candidate_keeps_its_diff(self):
        cases = {"new file": ({"create": ["home/dot_claude/skills/hiden/references/new.md"],
                               "result": {"structured_output": OUTPUT}}, "references/new.md"),
                 "foreign id": ({"edits": {SKILL: "skill v1\n"},
                                 "result": {"structured_output": {**OUTPUT, "evidence_ids": ["x"]}}}, "+skill v1")}
        for name, (spec, needle) in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                self.scenario(claude=spec)
                self.weekly()
                self.assertTrue(self.result()["outcome"].startswith("proposal:"))
                self.assertIn(needle, (self.k / improve.PROPOSALS / self.attempts()[0] / "diff.patch").read_text())

    def test_c2_the_lock_is_held_until_the_result_is_saved(self):
        real, probes = improve.save, []

        def probe(path, value):  # at the save of the final outcome, another taker must still be refused
            if str(value.get("outcome", "")).startswith("pr "):
                other = improve.take_lock(self.k)
                probes.append(other is None)
                if other:
                    other.close()
            real(path, value)
        with mock.patch.object(improve, "save", side_effect=probe):
            self.weekly()
        self.assertTrue(self.result()["outcome"].startswith("pr "))
        self.assertEqual(probes, [True])
        lock = improve.take_lock(self.k)
        self.assertIsNotNone(lock)
        lock.close()

    def test_c15_a_public_check_hit_is_a_proposal(self):
        self.scenario(public_check={"code": 1})
        self.weekly()
        self.assertEqual(self.result()["outcome"], "proposal:public-check")
        self.assertEqual(self.calls("codex"), [])
        self.assertNoWrites()

    def test_c15_bytes_changed_after_the_check_are_not_published(self):
        self.scenario(codex={"verdict": {"high": []}, "tamper": {f"{self.k}/proposals/*/body.md": "TAMPERED\n"}})
        self.weekly()
        self.assertEqual(self.result()["outcome"], "failed:frozen")
        self.assertNoWrites()

    # ---------------------------------------------------------------- C18, C19: remote writes and recovery
    def test_c18_the_push_is_create_only(self):
        branch_ref = None
        # the server already holds a ref at the branch name this attempt will use: fix the id
        with mock.patch.object(improve.os, "urandom", return_value=b"\xab\xcd\xef"):
            branch_ref = "refs/heads/kaizen/improve-20261119-abcdef"
            db = self.db()
            db["server"][branch_ref] = "d" * 40
            self.db(db)
            self.weekly()
        [push] = self.git_calls("push")
        self.assertIn("--force-with-lease=refs/heads/kaizen/improve-20261119-abcdef:", push["argv"])
        self.assertEqual(self.db()["server"][branch_ref], "d" * 40)  # never overwritten
        self.assertEqual(self.result()["outcome"], "publishing")
        res = self.weekly(now=NOW + timedelta(days=1))  # recovery: no PR, the ref at another commit
        self.assertEqual(self.result()["outcome"], improve.REMOTE_UNKNOWN)
        self.assertIn("another commit", self.result()["reason"])
        self.assertTrue(any("kaizen/improve-20261119-abcdef" in d for d in res["decisions"]))
        self.assertEqual(self.db()["server"][branch_ref], "d" * 40)

    def test_c18_a_push_timeout_leaves_publishing_with_the_fields(self):
        self.scenario(push={"sleep": 10})
        with mock.patch.dict(improve.SECONDS, {"push": 1}):
            self.weekly()
        r = self.result()
        self.assertEqual(r["outcome"], "publishing")
        self.assertEqual({k: r["remote"][k] for k in ("repo", "ref", "oid", "push_dispatched")},
                         {"repo": "o/r", "ref": f"refs/heads/{r['branch']}", "oid": r["oid"], "push_dispatched": True})
        self.assertNotIn("pr_dispatched", r["remote"])

    def test_c18_push_succeeded_server_side_then_one_recovery_create(self):
        self.scenario(push={"code": 1, "server": True})
        self.weekly()
        r = self.result()
        self.assertEqual(r["outcome"], "publishing")
        branch = r["branch"]
        self.scenario(lookup=[[[]], [[pr(r["oid"], ref=branch)]]])
        self.weekly(now=NOW + timedelta(days=1))
        after = self.result()
        self.assertEqual(after["outcome"], "pr https://github.com/o/r/pull/9")
        self.assertTrue(after["remote"]["recovery_dispatched"])
        self.assertEqual(len(self.jsonl("created.jsonl")), 1)  # only the recovery create; the first run made none
        self.assertEqual(len(self.jsonl("checked.jsonl")), 2)  # public-check again on the frozen inputs

    def test_c18_create_succeeded_server_side_is_adopted(self):
        for state in ("open", "closed"):
            with self.subTest(state):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                (self.fdir / "created.jsonl").unlink(missing_ok=True)
                self.scenario(create={"code": 1, "server": False}, lookup=["fail"])
                self.weekly()
                r = self.result()
                self.assertEqual(r["outcome"], "publishing")
                self.scenario(lookup=[[[pr(r["oid"], ref=r["branch"], state=state, number=12)]]])
                self.weekly(now=NOW + timedelta(days=1))
                self.assertEqual(self.result()["outcome"], "pr https://github.com/o/r/pull/12")
                self.assertEqual(len(self.jsonl("created.jsonl")), 1)  # no second create

    def test_c18_the_first_create_is_confirmed_by_the_head_oid(self):
        self.scenario(create={"stdout": "https://github.com/o/r/pull/9\n", "head_sha": "e" * 40})
        res = self.weekly()
        self.assertEqual(self.result()["outcome"], improve.REMOTE_UNKNOWN)  # gh said yes; the PR head is not ours
        self.assertTrue(any(self.result()["branch"] in d for d in res["decisions"]))

    def test_c18_a_lookup_failure_after_create_stays_publishing(self):
        self.scenario(lookup=["fail"])
        res = self.weekly()
        self.assertEqual(self.result()["outcome"], "publishing")
        self.assertTrue(any("is publishing" in d and self.result()["branch"] in d for d in res["decisions"]))
        self.scenario(lookup="auto", keep=True)
        self.weekly(now=NOW + timedelta(days=1))
        self.assertEqual(self.result()["outcome"], "pr https://github.com/o/r/pull/9")
        self.assertEqual(len(self.jsonl("created.jsonl")), 1)

    def test_c18_a_recovery_create_is_confirmed_before_success(self):
        a, r = self.publishing()
        self.scenario(lookup=[[[]], {"sleep": 30}])  # empty, then the confirming lookup hangs past the deadline
        res = self.weekly(seconds=4)
        self.assertEqual(res["status"], "skipped:deadline in recovery")
        after = self.result(a.data["id"])
        self.assertEqual(after["outcome"], "publishing")
        self.assertTrue(after["remote"]["recovery_dispatched"])
        self.assertEqual(len(self.jsonl("created.jsonl")), 1)

    def test_c18_recovery_uses_the_recorded_repo(self):
        a, r = self.publishing()
        self.scenario(open=["fail"])  # stop at the gate after the recovery
        self.weekly(slug="o/new-repo")  # the checkout's origin moved since the push
        [created] = self.jsonl("created.jsonl")
        self.assertEqual(created["argv"][created["argv"].index("--repo") + 1], "o/r")
        lookups = [c["argv"][-1] for c in self.calls("gh") if "state=all" in c["argv"][-1]]
        self.assertTrue(lookups and all(u.startswith("repos/o/r/pulls") for u in lookups), lookups)
        self.assertEqual(self.result(a.data["id"])["outcome"], "pr https://github.com/o/r/pull/9")

    def test_c18_recovery_without_a_checkout_is_a_decision(self):
        a, r = self.publishing()
        self.scenario(open=["fail"])
        res = improve.weekly(self.k, self.home, None, "o/r", [PUBLIC], READY, NOW, time.monotonic() + 60,
                             sources={"gh": {"status": "ok"}})
        after = self.result(a.data["id"])
        self.assertEqual(after["outcome"], improve.REMOTE_UNKNOWN)
        self.assertIn("checkout", after["reason"])
        self.assertTrue(any(r["branch"] in d and "cycle.py clear" in d for d in res["decisions"]), res["decisions"])
        self.assertEqual(self.jsonl("created.jsonl"), [])

    def test_c18_a_tree_that_cannot_be_removed_does_not_stop_recovery(self):
        a, r = self.publishing()
        tree = self.home / improve.STATE / "tree-left"
        tree.mkdir()
        a.update(tree=str(tree))
        self.scenario(open=["fail"])
        with mock.patch.object(improve.shutil, "rmtree", side_effect=PermissionError("denied")) as rmtree:
            self.weekly()
        rmtree.assert_called_once()
        self.assertEqual(self.result(a.data["id"])["outcome"], "pr https://github.com/o/r/pull/9")

    def test_c18_an_unexpected_recovery_error_is_a_decision(self):
        a, r = self.publishing()
        self.scenario(open=["fail"])
        with mock.patch.object(improve.Stage, "lookup", side_effect=RuntimeError("boom")):
            res = self.weekly()
        after = self.result(a.data["id"])
        self.assertEqual(after["outcome"], improve.REMOTE_UNKNOWN)
        self.assertIn("RuntimeError: boom", after["reason"])
        self.assertTrue(any(r["branch"] in d for d in res["decisions"]))

    def test_c18_ambiguous_remote_state_is_a_decision(self):
        cases = {"another oid": lambda r: [[pr("e" * 40, ref=r["branch"])]],
                 "another base": lambda r: [[pr(r["oid"], ref=r["branch"], base="dev")]],
                 "a fork head": lambda r: [[pr(r["oid"], ref=r["branch"], repo="someone/r")]],
                 "two matches": lambda r: [[pr(r["oid"], ref=r["branch"], number=1)],
                                           [pr(r["oid"], ref=r["branch"], number=2)]],
                 "lookup fails": lambda r: "fail"}
        for name, pages in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                a, r = self.publishing()
                self.scenario(lookup=[pages(r)])
                res = self.weekly()
                self.assertEqual(self.result()["outcome"], improve.REMOTE_UNKNOWN)
                self.assertTrue(any(r["branch"] in d for d in res["decisions"]))
                self.assertEqual(self.jsonl("created.jsonl"), [])
                self.assertEqual(self.db()["server"][r["ref"]], "c" * 40)

    def test_c18_ref_missing_or_after_a_recovery_create(self):
        for name in ("ref missing", "recovery already dispatched"):
            with self.subTest(name):
                shutil.rmtree(self.k / improve.PROPOSALS, ignore_errors=True)
                a, r = self.publishing(**({"recovery_dispatched": True} if name != "ref missing" else {}))
                if name == "ref missing":
                    db = self.db()
                    del db["server"][r["ref"]]
                    self.db(db)
                self.scenario(lookup=[[[]]])
                self.weekly()
                self.assertEqual(self.result()["outcome"], improve.REMOTE_UNKNOWN)
                self.assertEqual(self.jsonl("created.jsonl"), [])

    def test_c18_no_ref_is_ever_deleted(self):
        self.scenario(push={"code": 1, "server": False})
        self.weekly()
        self.weekly(now=NOW + timedelta(days=1))
        for call in self.git_calls("push"):
            self.assertNotIn("--delete", call["argv"])
            self.assertFalse(call["argv"][-1].startswith(":"))

    def test_c19_an_interrupted_attempt_fails_and_its_tree_goes(self):
        state = self.home / improve.STATE
        state.mkdir(parents=True)
        tree = Path(tempfile.mkdtemp(dir=state, prefix="tree-"))
        (tree / "f").write_text("x")
        outside = self.dir / "outside"
        outside.mkdir()
        self.old_attempt(outcome="started", tree=str(tree))
        self.scenario(open=["fail"])  # stop at the gate after recovery
        self.weekly()
        r = self.result()
        self.assertEqual((r["outcome"], r["cost_usd"]), ("failed:interrupted", "unknown"))
        self.assertFalse(tree.exists())
        self.assertTrue(outside.exists())

    def test_c19_an_interrupted_attempt_keeps_a_recorded_cost(self):
        self.old_attempt(outcome="started", cost_usd=4.0)
        self.scenario(open=["fail"])
        self.weekly()
        self.assertEqual((self.result()["outcome"], self.result()["cost_usd"]), ("failed:interrupted", 4.0))

    def test_c19_a_recorded_path_outside_the_state_dir_is_left(self):
        outside = self.dir / "tree-outside"
        outside.mkdir()
        self.old_attempt(outcome="started", tree=str(outside))
        self.scenario(open=["fail"])
        self.weekly()
        self.assertTrue(outside.exists())


DRIVER = """
import importlib.util, json, sys
from pathlib import Path
home, checkout, watch = map(Path, sys.argv[1:4])
spec = importlib.util.spec_from_file_location("cycle", sys.argv[4])
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)
item = json.loads(sys.argv[5])
cycle.observe.observe = lambda *a, **kw: {"window": {"since": "s", "until": "u"}, "sources": {}, "counts": {},
                                          "tally": {"owner": 0, "unknown": 0, "synthetic": 0}, "codex_sessions": {},
                                          "items": [item]}
cycle.ready.source_repo = lambda *a: checkout
cycle.main(["--home", str(home), "--watch-file", str(watch), "--no-apply", "--no-t3", "--chezmoi", "false",
            "--launchctl", "false", "--deadline", sys.argv[6]])
"""


class CycleRun(Fakes):
    def test_c11_the_run_publishes_with_the_attempt_failed_and_claude_dead(self):
        grandchild = self.fdir / "grandchild.pid"
        self.scenario(claude={"sleep": 300, "grandchild": str(grandchild)})
        watch = self.dir / "watch.json"
        watch.write_text("[]")
        driver = self.dir / "driver.py"
        driver.write_text(DRIVER)
        started = time.monotonic()
        p = subprocess.run([sys.executable, str(driver), str(self.home), str(self.repo), str(watch),
                            str(REPO / "scripts/kaizen/cycle.py"), json.dumps(PUBLIC), "135"],
                           capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
                           env={**os.environ, "KAIZEN_HOME": str(self.k)})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertLess(time.monotonic() - started, 60)
        pid = int(grandchild.read_text())
        self.addCleanup(lambda: alive(pid) and os.kill(pid, signal.SIGKILL))
        self.assertFalse(alive(pid))
        record = json.loads((self.k / "current/record.json").read_text())
        self.assertEqual(record["improver"]["attempt"]["outcome"], "failed:timeout")
        self.assertEqual(record["cost"]["claude_usd"], "unknown")
        self.assertIn("failed:timeout", (self.k / "current/digest.md").read_text())
        self.assertNoWrites()


class Shared(unittest.TestCase):
    def test_open_kaizen_prs_flattens_pages(self):
        pages = json.dumps([[pr("a", ref="kaizen/a", number=1)], [pr("b", ref="kaizen/b", repo="x/r", number=2),
                                                                   pr("c", ref="other", number=3)]])
        got = improve.ready.open_kaizen_prs("O/R", runner=lambda argv: (0, pages, ""))
        self.assertEqual([p["number"] for p in got], [1])
        with self.assertRaises(ValueError):
            improve.ready.open_kaizen_prs("o/r", runner=lambda argv: (0, json.dumps([pr("a")]), ""))
        with self.assertRaises(ValueError):
            improve.ready.open_kaizen_prs("o/r", runner=lambda argv: (1, "", "boom"))


if __name__ == "__main__":
    unittest.main()
