from datetime import datetime, timedelta, timezone
from pathlib import Path
import contextlib
import fcntl
import importlib.util
import io
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[1]
KAIZEN = REPO / "scripts/kaizen"
NOW = datetime(2026, 11, 19, 3, 0, tzinfo=timezone.utc)
SINCE = NOW - timedelta(days=7)


def load(name):
    spec = importlib.util.spec_from_file_location(f"test_kaizen_{name}", KAIZEN / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cycle = load("cycle")
observe, ready = cycle.observe, cycle.ready


def ts(t):
    return t.isoformat().replace("+00:00", "Z")


DISPATCH = None


def setUpModule():
    # One executable that every fake links to: macOS scans each new executable on its first run, which takes seconds
    global DISPATCH
    DISPATCH = Path(tempfile.mkdtemp()) / "dispatch"
    DISPATCH.write_text('#!/bin/sh\n. "$0.body"\n')
    DISPATCH.chmod(0o755)


def tearDownModule():
    shutil.rmtree(DISPATCH.parent)


def fake(directory, name, body):
    """A command standing in for a real one: a link to the dispatcher, which sources <link>.body."""
    path = Path(directory) / name
    path.symlink_to(DISPATCH)
    Path(f"{path}.body").write_text(body)
    return str(path)


class Temp(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)


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


class Transcripts(Temp):
    def session(self, records, name="s1", subagent=False, tail=b""):
        folder = self.dir / "projects" / "-p" / (f"{name}/subagents" if subagent else "")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (f"agent-{name}.jsonl" if subagent else f"{name}.jsonl")
        path.write_bytes(b"".join(json.dumps(r).encode() + b"\n" for r in records) + tail)
        return path

    def run_observe(self):
        paths = {"projects": self.dir / "projects", "t3_db": None, "codex": self.dir / "codex",
                 "ledgers": self.dir / "ledgers", "hiden": self.dir / "hiden"}
        (self.dir / "codex").mkdir(exist_ok=True)
        return observe.observe(paths, SINCE, NOW, gh=None)

    @staticmethod
    def user(text, t, human=True, **extra):
        r = {"type": "user", "timestamp": ts(t), "cwd": "/w", "message": {"role": "user", "content": text}, **extra}
        if human:
            r["origin"] = {"kind": "human"}
        return r

    @staticmethod
    def assistant(t, *tools):
        content = [{"type": "tool_use", "id": f"t{i}", "name": n, "input": a} for i, (n, a) in enumerate(tools)]
        return {"type": "assistant", "timestamp": ts(t), "cwd": "/w",
                "message": {"role": "assistant", "content": content or [{"type": "text", "text": "ok"}]}}

    def test_short_owner_reply_after_an_assistant_turn_is_a_candidate(self):
        t = NOW - timedelta(hours=1)
        self.session([self.user("do the task", t), self.assistant(t), self.user("no, the other one", t),
                      self.user("injected", t, human=False), self.user("x" * 301, t)])
        out = self.run_observe()
        self.assertEqual([i["excerpt"] for i in out["items"] if i["signal"] == "owner-reply"], ["no, the other one"])
        self.assertEqual(out["tally"]["owner"], 3)

    def test_unterminated_last_line_is_skipped_not_bad(self):
        t = NOW - timedelta(hours=1)
        self.session([self.user("task", t), self.assistant(t)],
                     tail=json.dumps(self.user("late reply", t)).encode())
        out = self.run_observe()
        self.assertEqual(out["counts"]["owner-reply"], 0)
        self.assertEqual(out["sources"]["transcripts"]["bad_lines"], 0)
        self.assertEqual(out["sources"]["transcripts"]["status"], "ok")

    def test_window_is_half_open(self):
        t = SINCE + timedelta(hours=1)
        self.session([self.user("task", t), self.assistant(t), self.user("at since", SINCE),
                      self.user("at until", NOW), self.user("before since", SINCE - timedelta(seconds=1))])
        self.assertEqual([i["excerpt"] for i in self.run_observe()["items"] if i["signal"] == "owner-reply"],
                         ["at since"])

    def test_a_fifo_is_not_opened(self):
        self.session([self.user("task", NOW - timedelta(hours=1))])
        os.mkfifo(self.dir / "projects/-p/stuck.jsonl")
        with no_hang():
            out = self.run_observe()
        self.assertEqual(out["sources"]["transcripts"]["status"], "fail")
        self.assertIn("not a regular file", out["sources"]["transcripts"]["error"])
        self.assertEqual(out["sources"]["transcripts"]["files"], 1)

    def test_t3_session_utterances_come_only_from_the_database(self):
        t = NOW - timedelta(hours=1)
        self.session([{**self.user("task", t), "entrypoint": "t3-code"}, self.assistant(t),
                      {**self.user("reply", t), "entrypoint": "t3-code"}])
        out = self.run_observe()
        self.assertEqual(out["counts"]["owner-reply"], 0)
        self.assertEqual(out["tally"]["unknown"], 1)  # the T3 source is off, so the session is unresolved

    def test_waste_signals(self):
        t = NOW - timedelta(hours=1)
        (self.dir / "hiden/references").mkdir(parents=True)
        for name in ("read.md", "unread.md"):
            (self.dir / "hiden/references" / name).write_text("x")
        self.session([self.user("task", t), self.assistant(
            t, ("Read", {"file_path": "/h/.claude/skills/hiden/references/read.md"}),
            ("Bash", {"command": "cat ~/.claude/review-ledgers/x.md"}))])
        self.session([self.assistant(t, ("Skill", {"skill": "hiden"}))], name="w", subagent=True)
        out = self.run_observe()
        self.assertEqual({s: out["counts"][s] for s in ("meta-effort", "hiden-in-worker", "reference-unread")},
                         {"meta-effort": 1, "hiden-in-worker": 1, "reference-unread": 1})
        self.assertIn("unread.md", next(i for i in out["items"] if i["signal"] == "reference-unread")["where"])

    def test_missing_codex_root_fails_only_that_source(self):
        out = self.run_observe()
        shutil.rmtree(self.dir / "codex")
        out = observe.observe({"projects": self.dir / "projects", "t3_db": None, "codex": self.dir / "codex",
                               "ledgers": self.dir / "ledgers", "hiden": self.dir / "hiden"}, SINCE, NOW, gh=None)
        self.assertEqual(out["sources"]["codex"]["status"], "fail")
        self.assertEqual(out["sources"]["transcripts"]["status"], "fail")  # no projects root either
        self.assertEqual(out["sources"]["ledgers"]["status"], "ok")

    def test_codex_sessions_and_ledger_misses(self):
        (self.dir / "projects").mkdir()
        codex = self.dir / "codex/2026/11/18"
        codex.mkdir(parents=True)
        (codex / "rollout-a.jsonl").write_text(json.dumps({"payload": {"timestamp": ts(NOW - timedelta(hours=2)),
                                                                       "cwd": "/repo"}}) + "\n")
        (self.dir / "ledgers").mkdir()
        # the window is 12:00 Nov 12 to 12:00 Nov 19 in Asia/Tokyo; a ledger day counts when its start lies in it
        (self.dir / "ledgers/x.md").write_text("".join(f"- 2026-11-{d} r: 見逃し 1 day {d}\n" for d in (12, 13, 19, 20))
                                               + "- 2026-11-18 r2: 見逃し 0\n")
        out = self.run_observe()
        self.assertEqual(out["codex_sessions"], {"/repo": 1})
        self.assertEqual(sorted(i["excerpt"][-6:] for i in out["items"] if i["signal"] == "ledger-miss"),
                         ["day 13", "day 19"])


class T3(Temp):
    def db(self):
        path = self.dir / "state#1.sqlite"
        conn = sqlite3.connect(path)
        conn.execute("create table orchestration_v2_projection_threads (thread_id text, payload_json text)")
        conn.execute("create table orchestration_v2_projection_messages (thread_id text, role text, created_at text,"
                     " payload_json text)")
        conn.executemany("insert into orchestration_v2_projection_threads values (?, ?)", [
            ("root", "{}"), ("child", json.dumps({"lineage": {"parentThreadId": "root",
                                                              "relationshipToParent": "child"}}))])
        t = lambda m: observe.db_time(NOW - timedelta(minutes=m))
        rows = [("root", "user", t(50), {"createdBy": "user", "creationSource": "web", "text": "task", "id": "1"}),
                ("root", "assistant", t(40), {"text": "done"}),
                ("root", "user", t(30), {"createdBy": "user", "creationSource": "web", "text": "not that", "id": "2"}),
                ("root", "user", t(20), {"createdBy": "user", "creationSource": "server", "text": "q?", "id": "3"}),
                ("root", "user", t(15), {"createdBy": "user", "creationSource": "web", "text": "/compact", "id": "4"}),
                ("child", "user", t(10), {"createdBy": "user", "creationSource": "web", "text": "hi", "id": "5"}),
                ("root", "user", t(0), {"createdBy": "user", "creationSource": "web", "text": "at until", "id": "6"})]
        conn.executemany("insert into orchestration_v2_projection_messages values (?, ?, ?, ?)",
                         [(a, b, c, json.dumps(d)) for a, b, c, d in rows])
        conn.commit()
        conn.close()
        return path

    def test_owner_rows_of_root_threads_after_an_assistant_turn(self):
        path = self.db()
        before = path.read_bytes()  # SQLite may add -wal and -shm beside it (accepted); the database stays as it was
        out = {"items": [], "tally": {"owner": 0, "unknown": 0, "synthetic": 0}}
        observe.observe_t3(path, SINCE, NOW, out, observe.Source("t3"))
        self.assertEqual([i["excerpt"] for i in out["items"]], ["not that"])
        self.assertEqual(out["tally"], {"owner": 2, "unknown": 2, "synthetic": 1})
        self.assertEqual(path.read_bytes(), before)


GH = """case "$1 $2" in
  "repo view") echo '{"visibility":"PUBLIC","defaultBranchRef":{"name":"main"}}' ;;
  "pr list") echo '[{"number":5,"title":"Revert x","body":"","mergedAt":"%(t)s","url":"u5"},
             {"number":6,"title":"fix y","body":"fixes #5 and #99","mergedAt":"%(t)s","url":"u6"},
             {"number":7,"title":"Revert late","body":"fixes #5","mergedAt":"%(late)s","url":"u7"}]' ;;
  "run list") echo '[{"displayTitle":"t","createdAt":"%(t)s","url":"r1","workflowName":"CI"},
             {"displayTitle":"late","createdAt":"%(late)s","url":"r2","workflowName":"CI"}]' ;;
  "auth status") exit 0 ;;
  *) exit 1 ;;
esac
"""


class Gh(Temp):
    def test_reverts_fix_prs_and_main_failures(self):
        gh = fake(self.dir, "gh", GH % {"t": ts(NOW - timedelta(hours=1)), "late": ts(NOW)})
        out = {"items": [], "cwds": {"/repo": 1}}
        with mock.patch.object(observe, "origin_repo", return_value="o/r"):
            observe.observe_gh(gh, SINCE, NOW, out, observe.Source("gh"))
        found = {i["signal"]: i for i in out["items"]}
        self.assertEqual(sorted(i["signal"] for i in out["items"]), ["ci-fail-main", "fix-pr", "revert"])  # not at NOW
        self.assertIn("fixes #5)", found["fix-pr"]["excerpt"])  # #99 is no merged PR in the window
        self.assertEqual(found["revert"]["provenance"], "public")

    def test_gh_failure_fails_only_gh(self):
        gh = fake(self.dir, "gh", "echo boom >&2; exit 1\n")
        (self.dir / "codex").mkdir()
        (self.dir / "projects").mkdir()
        paths = {"projects": self.dir / "projects", "t3_db": None, "codex": self.dir / "codex",
                 "ledgers": self.dir / "ledgers", "hiden": self.dir / "hiden"}
        with mock.patch.object(observe, "observe_codex", side_effect=lambda r, s, u, o, src: o["cwds"].update(
                {"/repo": 1})), mock.patch.object(observe, "origin_repo", return_value="o/r"):
            out = observe.observe(paths, SINCE, NOW, gh=gh)
        self.assertEqual(out["sources"]["gh"]["status"], "fail")
        self.assertIn("boom", out["sources"]["gh"]["error"])
        self.assertEqual(out["sources"]["transcripts"]["status"], "ok")


LAUNCHCTL_PRINT = """gui/501/org.nix-community.home.kaizen-cycle = {
\tactive count = 0
\tpath = ~/Library/LaunchAgents/org.nix-community.home.kaizen-cycle.plist
\tstate = not running

\tprogram = /bin/sh
\targuments = {
\t\t/bin/sh
\t\t-c
\t\t%(wait)s && exec %(program)s %(script)s
\t}

\tstdout path = ~/Library/Logs/kaizen-cycle.log
}
"""


class Ready(Temp):
    """R2 reads the shape Home Manager gives a launchd agent: /bin/sh -c "/bin/wait4path /nix/store && exec ..."."""

    def test_parse_launchctl(self):
        text = LAUNCHCTL_PRINT % {"wait": "/bin/wait4path /nix/store", "program": "/nix/store/p/bin/python3",
                                  "script": "/nix/store/k/cycle.py"}
        program, args = ready.parse_launchctl(text)
        self.assertEqual(program, "/bin/sh")
        self.assertEqual(args[2], "/bin/wait4path /nix/store && exec /nix/store/p/bin/python3 /nix/store/k/cycle.py")
        self.assertEqual([p for a in args for p in ready.ABSOLUTE.findall(a)],
                         ["/bin/sh", "/bin/wait4path", "/nix/store", "/nix/store/p/bin/python3",
                          "/nix/store/k/cycle.py"])

    def launchctl(self, script, code=0):
        text = LAUNCHCTL_PRINT % {"wait": f"/bin/test -d {self.dir}", "program": sys.executable, "script": script}
        (self.dir / "print.txt").write_text(text)
        return fake(self.dir, "launchctl", f'cat "{self.dir}/print.txt"; exit {code}\n')

    def test_r2_passes_when_loaded_and_paths_exist(self):
        self.assertEqual(ready.check_r2(self.launchctl(__file__))["status"], "PASS")

    def test_r2_fails_when_the_script_is_gone(self):
        r = ready.check_r2(self.launchctl("/nonexistent/cycle.py"))
        self.assertEqual((r["status"], r["owner"]), ("FAIL", True))
        self.assertIn("missing: /nonexistent/cycle.py", r["detail"])

    def test_r2_fails_when_not_loaded(self):
        r = ready.check_r2(fake(self.dir, "launchctl", "echo 'Could not find service' >&2; exit 113\n"))
        self.assertEqual(r["status"], "FAIL")
        self.assertIn("not loaded", r["detail"])

    def r1(self, managed, diff):
        """check_r1 against a fake chezmoi whose `managed` prints the shape chezmoi 2.70 prints for
        --include=files,symlinks,remove --path-style=all --format=json, and whose `diff` prints `diff`."""
        repo = self.dir / "repo"
        (repo / ".claude").mkdir(parents=True)
        (repo / ".claude/kaizen-managed").write_text("# list\nhome/dot_claude/**\nhome/.chezmoiremove\n")
        source = repo / "home"
        entries = {rel: {"absolute": str(self.dir / "h" / rel), "sourceAbsolute": str(source / src),
                         "sourceRelative": src} for rel, src in managed.items()}
        (self.dir / "managed.json").write_text(json.dumps(entries))
        (self.dir / "diff.txt").write_text(diff)
        chezmoi = fake(self.dir, "chezmoi", f"""case "$3" in
  managed) cat "{self.dir}/managed.json" ;;
  diff) echo "$@" > "{self.dir}/diff-args"; cat "{self.dir}/diff.txt" ;;
esac
""")
        return ready.check_r1(self.dir / "h", repo, chezmoi), (self.dir / "diff-args").read_text()

    def test_r1_lists_differing_managed_targets(self):
        r, args = self.r1({".claude/a": "dot_claude/a", ".zshrc": "dot_zshrc"},
                          "diff --git a/.claude/a b/.claude/a\n-x\n+y\n")
        self.assertEqual((r["status"], r["detail"]), ("FAIL", [".claude/a"]))
        self.assertNotIn(".zshrc", args)

    def test_r1_sees_a_pending_removal(self):
        # a .chezmoiremove entry: empty sourceRelative, the source directory as sourceAbsolute; diff shows it deleted
        r, args = self.r1({".claude/a": "dot_claude/a", ".claude/gone": ""},
                          "diff --git a/.claude/gone b/.claude/gone\ndeleted file mode 100644\n")
        self.assertIn(".claude/gone", args)
        self.assertEqual((r["status"], r["detail"]), ("FAIL", [".claude/gone"]))

    def test_r3_fails_on_over(self):
        hooks = self.dir / ".claude/hooks"
        hooks.mkdir(parents=True)
        fake(hooks, "attention-budget.py", "echo 'OVER: x is 9 bytes; cap 1'; exit 1\n")
        self.assertEqual(ready.check_r3(self.dir)["detail"], ["OVER: x is 9 bytes; cap 1"])

    def test_r4_owner_when_gh_is_not_authenticated(self):
        gh = fake(self.dir, "gh", "exit 1\n")
        r = ready.check_r4({"transcripts": {"status": "ok"}, "gh": {"status": "off"}}, gh)
        self.assertEqual((r["status"], r["owner"]), ("FAIL", True))
        r = ready.check_r4({"transcripts": {"status": "fail", "error": "e"}}, fake(self.dir, "gh2", "exit 0\n"))
        self.assertEqual((r["status"], r["owner"]), ("FAIL", False))

    def test_r5_old_run_and_old_kaizen_pr(self):
        empty = fake(self.dir, "gh3", "echo '[]'\n")
        self.assertEqual(ready.check_r5(self.dir, NOW, "o/r", empty), ready.result(True, "first run"))
        (self.dir / "current").mkdir()
        (self.dir / "current/record.json").write_text(json.dumps({"finished": ts(NOW - timedelta(days=5))}))
        prs = [{"number": 1, "headRefName": "kaizen/x", "createdAt": ts(NOW - timedelta(days=20))},
               {"number": 2, "headRefName": "other", "createdAt": ts(NOW - timedelta(days=20))}]
        r = ready.check_r5(self.dir, NOW, "o/r", fake(self.dir, "gh", f"echo '{json.dumps(prs)}'\n"))
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(len(r["detail"]), 2)
        (self.dir / "current/record.json").write_text(json.dumps({"finished": ts(NOW - timedelta(days=1))}))
        self.assertEqual(ready.check_r5(self.dir, NOW, "o/r", empty)["status"], "PASS")


class Cycle(Temp):
    """Whole runs with fake commands and an empty home."""

    def setUp(self):
        super().setUp()
        self.home = self.dir / "home"
        for d in (".claude/projects", ".codex/sessions", ".claude/hooks"):
            (self.home / d).mkdir(parents=True)
        fake(self.home / ".claude/hooks", "attention-budget.py", "exit 0\n")
        self.k = self.dir / "k"
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        self.watch = self.dir / "watch.json"
        self.watch.write_text(json.dumps([{"change": "#1", "signal": "regression", "apply": ts(NOW - timedelta(days=2)),
                                           "days": 28}]))
        self.args = ["--home", str(self.home), "--watch-file", str(self.watch), "--no-t3",
                     "--gh", fake(self.bin, "gh", "case \"$1\" in pr) echo '[]';; esac; exit 0\n"),
                     "--chezmoi", fake(self.bin, "chezmoi", "exit 1\n"),
                     "--launchctl", fake(self.bin, "launchctl", "exit 113\n")]

    def main(self, *extra, now=NOW):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"KAIZEN_HOME": str(self.k)}), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            cycle.main([*extra, *self.args], now=now)
        return json.loads(out.getvalue().splitlines()[-1])

    def outputs(self):
        """What a reader can see: where K/current points, and every file under K."""
        current = self.k / "current"
        files = {p.relative_to(self.k).as_posix(): p.read_bytes() for p in sorted(self.k.rglob("*"))
                 if p.is_file() and not p.is_symlink() and p.name != ".publish.lock"}
        return (os.readlink(current) if current.is_symlink() else None), files

    def published(self, name):
        return json.loads((self.k / "current" / name).read_text())

    def test_run_publishes_one_directory(self):
        summary = self.main()
        target, files = self.outputs()
        self.assertEqual(sorted(files), [f"{target}/{n}" for n in ("digest.md", "record.json", "status.json")])
        self.assertEqual(sorted(p.name for p in self.k.iterdir()), [".publish.lock", "current", "runs"])
        status = self.published("status.json")
        self.assertEqual((status["fail"], status["decisions"]), (summary["fail"], summary["decisions"]))
        self.assertGreaterEqual(status["fail"], 2)  # R1 (no chezmoi source) and R2 (job not loaded)
        record = self.published("record.json")
        self.assertEqual((record["date"], record["cost"]), ("2026-11-19", {"claude_usd": 0, "codex_usd": 0}))
        self.assertEqual(record["watch"][0]["pre_source"], "live, partial: older transcripts deleted")
        digest = (self.k / "current/digest.md").read_text()
        for section in ("## 準備状態", "## 取りこぼしと無駄", "## 監視中の変更", "## 判断事項", "## 費用"):
            self.assertIn(section, digest)

    def test_a_failed_publish_step_leaves_the_previous_run(self):
        self.main()
        before = self.outputs()
        real = os.replace

        def full(src, dst):
            if Path(dst).name in ("current", "status.json"):
                raise OSError(28, "No space left on device")
            return real(src, dst)

        with mock.patch.object(cycle.os, "replace", side_effect=full), self.assertRaises(OSError):
            self.main(now=NOW + timedelta(days=1))
        self.assertEqual(self.outputs(), before)
        self.assertEqual(len(list((self.k / "runs").iterdir())), 1)
        self.assertEqual(sorted(p.name for p in self.k.iterdir()), [".publish.lock", "current", "runs"])

    def test_publish_keeps_the_published_and_the_previous_run(self):
        targets = []
        for day in range(3):
            self.main(now=NOW + timedelta(days=day))
            targets.append(os.readlink(self.k / "current"))
        (self.k / "runs/notes").mkdir()  # not a run directory: left alone
        self.main(now=NOW + timedelta(days=3))
        targets.append(os.readlink(self.k / "current"))
        self.assertEqual(sorted(p.name for p in (self.k / "runs").iterdir()),
                         sorted([Path(targets[-1]).name, Path(targets[-2]).name, "notes"]))

    def test_a_stop_right_after_the_rename_keeps_the_publish(self):
        real = os.replace

        def then_stop(src, dst):
            real(src, dst)
            if Path(dst).name == "current":
                os.kill(os.getpid(), signal.SIGTERM)

        with mock.patch.object(cycle.os, "replace", side_effect=then_stop), self.assertRaises(SystemExit):
            self.main()
        self.assertTrue((self.k / "current/status.json").is_file())

    def test_publishers_take_turns(self):
        self.main()
        before = os.readlink(self.k / "current")
        done = []
        with open(self.k / ".publish.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)  # another publisher is mid-publish
            t = threading.Thread(target=lambda: done.append(cycle.publish_run(self.k, {}, {"status.json": "{}"}).name))
            t.start()
            t.join(0.5)
            self.assertEqual((os.readlink(self.k / "current"), done), (before, []))
        t.join(10)
        self.assertEqual(Path(os.readlink(self.k / "current")).name, done[0])
        self.assertEqual(sorted(p.name for p in (self.k / "runs").iterdir()), sorted([Path(before).name, done[0]]))

    def test_a_failed_prune_keeps_the_publish(self):
        self.main()
        oldest = (self.k / "current").resolve()  # neither the next run's previous nor its own: pruned by the third
        self.main(now=NOW + timedelta(days=1))
        oldest.chmod(0o500)
        self.addCleanup(oldest.chmod, 0o700)
        self.main(now=NOW + timedelta(days=2))
        self.assertTrue((self.k / "current/status.json").is_file())
        self.assertTrue(oldest.is_dir())

    def test_failed_run_leaves_previous_outputs(self):
        self.main()
        before = self.outputs()
        with mock.patch.object(cycle.observe, "observe", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.main(now=NOW + timedelta(days=1))
        self.assertEqual(self.outputs(), before)

    def test_interrupted_write_removes_its_temp_file(self):
        (self.k).mkdir()
        (self.k / "status.json").write_text("old")
        with self.assertRaises(TypeError):
            cycle.publish(self.k / "status.json", 123)
        self.assertEqual(sorted(p.name for p in self.k.iterdir()), ["status.json"])
        self.assertEqual((self.k / "status.json").read_text(), "old")

    def stopped_run(self, stop, *extra):
        """Run cycle.py in a child whose R2 hangs and call stop(proc) once it hangs; (exit code, stderr). The
        previous run stays published and no other run directory is left."""
        self.main()
        before = self.outputs()
        started = self.dir / "started"
        slow = fake(self.bin, "slow-launchctl", f'touch "{started}"; exec sleep 30\n')
        args = [a if a != self.args[-1] else slow for a in self.args]
        proc = subprocess.Popen([sys.executable, str(KAIZEN / "cycle.py"), *args, *extra], stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, text=True, env={**os.environ, "KAIZEN_HOME": str(self.k)})
        try:
            deadline = time.monotonic() + 60
            while not started.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(started.exists(), "the run did not reach R2")
            stop(proc)
            _, err = proc.communicate(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        self.assertEqual(self.outputs(), before)
        self.assertEqual(len(list((self.k / "runs").iterdir())), 1)
        return proc.returncode, err

    def test_a_run_waiting_for_the_lock_stops_unpublished(self):
        self.main()
        before = self.outputs()
        with open(self.k / ".publish.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)  # another publisher holds the lock past this run's deadline
            p = subprocess.run([sys.executable, str(KAIZEN / "cycle.py"), *self.args, "--deadline", "3"],
                               capture_output=True, text=True, timeout=120, env={**os.environ, "KAIZEN_HOME": str(self.k)})
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("passed its 3s deadline", p.stderr)
        self.assertEqual(self.outputs(), before)

    def test_sigterm_mid_run_keeps_previous_outputs(self):
        code, _ = self.stopped_run(lambda proc: proc.send_signal(signal.SIGTERM))
        self.assertEqual(code, 143)

    def test_a_run_past_its_deadline_exits_unpublished(self):
        code, err = self.stopped_run(lambda proc: None, "--deadline", "3")
        self.assertEqual(code, 1)
        self.assertIn("passed its 3s deadline", err)

    def test_baseline_is_written_once_and_used_by_the_run(self):
        first = self.main("baseline", "#1")
        self.assertTrue(first["written"])
        saved = (self.k / "watch/#1.json").read_bytes()
        self.assertFalse(self.main("baseline", "#1")["written"])
        self.assertEqual((self.k / "watch/#1.json").read_bytes(), saved)
        self.main()
        self.assertEqual(self.published("record.json")["watch"][0]["pre_source"], "snapshot")

    APPLIED = {"status": "stopped", "reason": None, "head": "f" * 40, "passed": 1,
               "cursor": {"commit": "a" * 40, "by": "cycle", "at": "2026-11-18T21:00:00Z"},
               "merges": [{"commit": "b" * 40, "pr": "#7", "status": "conflict", "reason": "live differs from both sides",
                           "targets": {".claude/skills/x/SKILL.md": "conflict: edited"}}],
               "journal": [], "decisions": ["apply: #7 (bbbbbbbb) not applied: live differs"]}

    def test_apply_runs_first_and_its_result_and_decisions_are_published(self):
        order = []
        real_observe = cycle.observe.observe
        with mock.patch.object(cycle.apply, "run", side_effect=lambda *a, **k: order.append("apply") or self.APPLIED), \
                mock.patch.object(cycle.observe, "observe",
                                  side_effect=lambda *a, **k: order.append("observe") or real_observe(*a, **k)):
            summary = self.main()
        self.assertEqual(order, ["apply", "observe"])
        record = self.published("record.json")
        self.assertEqual(record["apply"], self.APPLIED)
        self.assertIn(self.APPLIED["decisions"][0], record["decisions"])
        self.assertEqual(summary["decisions"], len(record["decisions"]))
        self.assertIn("transcripts", record["sources"])  # observe still ran
        digest = (self.k / "current/digest.md").read_text()
        self.assertIn("## 適用", digest)
        self.assertIn("位置: aaaaaaaaaaaa（cycle、2026-11-18T21:00:00Z）", digest)
        self.assertIn("#7 conflict", digest)

    def test_an_apply_exception_does_not_prevent_publication(self):
        state = self.home / ".local/state/kaizen-apply"
        state.mkdir(parents=True)
        (state / "applied.json").write_text(json.dumps({"commit": "c" * 40, "by": "owner", "at": "t", "run": None}))
        (state / "journal.json").write_text(json.dumps({"entries": [
            {"merge": "d" * 40, "target": ".claude/agents/w.md", "backup": "backup/r/m/.claude/agents/w.md",
             "step": "unresolved", "note": "swapped back", "expected_old_sha": "0" * 64, "new_sha": "1" * 64}]}))
        with mock.patch.object(cycle.apply, "run", side_effect=RuntimeError("boom")):
            self.main()
        record = self.published("record.json")
        self.assertEqual(record["apply"]["status"], "error")
        self.assertIn("apply crashed: RuntimeError: boom", record["decisions"])
        digest = (self.k / "current/digest.md").read_text()
        self.assertIn("位置: cccccccccccc（owner、t）", digest)  # the stored cursor and journal, always (N5)
        self.assertIn("未解決の journal: 1 件", digest)
        self.assertIn(".claude/agents/w.md（unresolved）", digest)
        self.assertIn("## 取りこぼしと無駄", digest)

    def test_invalid_apply_state_is_a_decision_and_the_run_publishes(self):
        state = self.home / ".local/state/kaizen-apply"
        state.mkdir(parents=True)
        (state / "applied.json").write_text('{"commit": "bad"}')
        self.main()
        record = self.published("record.json")
        self.assertEqual(record["apply"]["status"], "error")
        self.assertTrue(any("state invalid" in d for d in record["decisions"]))
        self.assertIn("適用の状態が読めない", (self.k / "current/digest.md").read_text())
        (state / "applied.json").unlink()
        (state / "journal.json").write_text("{")
        with mock.patch.object(cycle.apply, "run", side_effect=RuntimeError("boom")):
            self.main(now=NOW + timedelta(days=1))
        self.assertIn("適用の状態が読めない", (self.k / "current/digest.md").read_text())

    def test_a_slow_clone_leaves_time_to_observe_and_publish(self):
        checkout = self.dir / "checkout"
        checkout.mkdir()
        fake(self.bin, "git", 'case " $* " in\n  *" remote get-url "*) echo https://github.com/o/r.git ;;\n'
                              '  *" clone "*) exec sleep 60 ;;\nesac\n')
        started = time.monotonic()
        with mock.patch.object(cycle.ready, "source_repo", return_value=checkout), \
                mock.patch.object(cycle, "APPLY_RESERVE", 25), \
                mock.patch.dict(os.environ, {"PATH": f"{self.bin}:{os.environ['PATH']}"}):
            self.main("--deadline", "30")
        self.assertLess(time.monotonic() - started, 20)
        record = self.published("record.json")
        self.assertIn("timed out", record["apply"]["reason"])
        self.assertIn("transcripts", record["sources"])
        self.assertIn("R1", record["ready"])

    def test_no_apply_skips_the_stage(self):
        with mock.patch.object(cycle.apply, "run") as run:
            self.main("--no-apply")
        run.assert_not_called()
        self.assertEqual(self.published("record.json")["apply"]["status"], "off")
        self.assertIn("位置: 未設定", (self.k / "current/digest.md").read_text())

    def test_the_real_apply_stage_reports_a_missing_checkout(self):
        self.main()  # the fake chezmoi fails, so there is no origin to fetch; the run still publishes
        record = self.published("record.json")
        self.assertEqual(record["apply"]["status"], "error")
        self.assertTrue(any(d.startswith("apply: no checkout") for d in record["decisions"]))

    def test_resolve_and_adopt_commands(self):
        state = self.home / ".local/state/kaizen-apply"
        state.mkdir(parents=True)
        (state / "journal.json").write_text(json.dumps({"entries": [
            {"merge": "d" * 40, "target": ".claude/agents/w.md", "backup": "backup/r/m/.claude/agents/w.md",
             "step": "staged", "expected_old_sha": "0" * 64, "new_sha": "1" * 64}]}))
        self.assertEqual(self.main("resolve")["cleared"], False)
        self.assertEqual(self.main("resolve", "--yes")["cleared"], True)
        self.assertEqual(json.loads((state / "journal.json").read_text()), {"entries": []})
        with mock.patch.object(cycle.apply, "adopt", return_value={"adopted": "e" * 40}) as adopt:
            self.assertEqual(self.main("adopt", "e" * 40), {"adopted": "e" * 40})
        self.assertEqual(adopt.call_args.args[2], "e" * 40)

    def test_invalid_change_id_is_rejected(self):
        self.watch.write_text(json.dumps([{"change": "../x", "signal": "regression", "apply": ts(NOW)}]))
        with self.assertRaises(ValueError):
            self.main("baseline", "../x")


TEMPLATE = REPO / "home/dot_claude/executable_statusline.sh.tmpl"
STDIN = json.dumps({"workspace": {"current_dir": "/"}, "model": {"display_name": "M"},
                    "context_window": {"used_percentage": 1}})


@unittest.skipUnless(shutil.which("chezmoi") and shutil.which("jq"), "needs chezmoi and jq")
class Statusline(Temp):
    def setUp(self):
        super().setUp()
        with TEMPLATE.open() as tmpl:
            rendered = subprocess.run(["chezmoi", "--source", str(REPO / "home"), "execute-template"], stdin=tmpl,
                                      capture_output=True, text=True, check=True).stdout
        self.script = self.dir / "statusline.sh"
        self.script.write_text(rendered)
        self.script.chmod(0o755)

    def line(self, status=None):
        if status is not None:
            (self.dir / "current").mkdir(exist_ok=True)
            (self.dir / "current/status.json").write_text(status if isinstance(status, str) else json.dumps(status))
        out = subprocess.run([str(self.script)], input=STDIN, capture_output=True, text=True, cwd=self.dir,
                             env={**os.environ, "KAIZEN_HOME": str(self.dir)}, check=True, timeout=30).stdout
        return re.sub(r"\x1b\[[0-9;]*m", "", out)

    def test_failures_decisions_and_staleness(self):
        last = int(time.time()) - 3 * 86400 - 60
        self.assertIn("kaizen ✗1・判断 2・stale 3d", self.line({"fail": 1, "decisions": 2,
                                                                 "last_completed_epoch": last}))

    def test_stale_after_36_hours_only(self):
        now = int(time.time())
        self.assertNotIn("kaizen", self.line({"fail": 0, "decisions": 0, "last_completed_epoch": now - 35 * 3600}))
        self.assertIn("kaizen stale 1d", self.line({"fail": 0, "decisions": 0,
                                                     "last_completed_epoch": now - 37 * 3600}))

    def test_quiet_before_the_first_run_and_visible_when_unreadable(self):
        self.assertNotIn("kaizen", self.line())
        self.assertIn("kaizen ?", self.line("not json"))


if __name__ == "__main__":
    unittest.main()
