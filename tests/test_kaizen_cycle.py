from datetime import datetime, timedelta, timezone
from pathlib import Path
import contextlib
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

    def test_records_outside_the_window_do_not_count(self):
        old = SINCE - timedelta(hours=1)
        self.session([self.user("task", old), self.assistant(old), self.user("old reply", old)])
        self.assertEqual(self.run_observe()["counts"]["owner-reply"], 0)

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
        (self.dir / "ledgers/x.md").write_text("- 2026-11-18 r1: 見逃し 1 something\n- 2026-11-18 r2: 見逃し 0\n"
                                               "- 2026-10-01 r0: 見逃し 1 old\n")
        out = self.run_observe()
        self.assertEqual(out["codex_sessions"], {"/repo": 1})
        self.assertEqual(out["counts"]["ledger-miss"], 1)


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
                ("child", "user", t(10), {"createdBy": "user", "creationSource": "web", "text": "hi", "id": "5"})]
        conn.executemany("insert into orchestration_v2_projection_messages values (?, ?, ?, ?)",
                         [(a, b, c, json.dumps(d)) for a, b, c, d in rows])
        conn.commit()
        conn.close()
        return path

    def test_owner_rows_of_root_threads_after_an_assistant_turn(self):
        path = self.db()
        before = path.read_bytes()
        out = {"items": [], "tally": {"owner": 0, "unknown": 0, "synthetic": 0}}
        observe.observe_t3(path, SINCE, NOW, out, observe.Source("t3"))
        self.assertEqual([i["excerpt"] for i in out["items"]], ["not that"])
        self.assertEqual(out["tally"], {"owner": 2, "unknown": 2, "synthetic": 1})
        self.assertEqual(path.read_bytes(), before)


GH = """case "$1 $2" in
  "repo view") echo '{"visibility":"PUBLIC","defaultBranchRef":{"name":"main"}}' ;;
  "pr list") echo '[{"number":5,"title":"Revert x","body":"","mergedAt":"%(t)s","url":"u5"},
             {"number":6,"title":"fix y","body":"fixes #5 and #99","mergedAt":"%(t)s","url":"u6"}]' ;;
  "run list") echo '[{"displayTitle":"t","createdAt":"%(t)s","url":"r1","workflowName":"CI"}]' ;;
  "auth status") exit 0 ;;
  *) exit 1 ;;
esac
"""


class Gh(Temp):
    def test_reverts_fix_prs_and_main_failures(self):
        gh = fake(self.dir, "gh", GH % {"t": ts(NOW - timedelta(hours=1))})
        out = {"items": [], "cwds": {"/repo": 1}}
        with mock.patch.object(observe, "origin_repo", return_value="o/r"):
            observe.observe_gh(gh, SINCE, out, observe.Source("gh"))
        found = {i["signal"]: i for i in out["items"]}
        self.assertEqual(sorted(found), ["ci-fail-main", "fix-pr", "revert"])
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
\tpath = /Users/u/Library/LaunchAgents/org.nix-community.home.kaizen-cycle.plist
\tstate = not running

\tprogram = /bin/sh
\targuments = {
\t\t/bin/sh
\t\t-c
\t\t%(wait)s && exec %(program)s %(script)s
\t}

\tstdout path = /Users/u/Library/Logs/kaizen-cycle.log
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

    def test_r1_lists_differing_managed_targets(self):
        repo = self.dir / "repo"
        (repo / ".claude").mkdir(parents=True)
        (repo / ".claude/kaizen-managed").write_text("# list\nhome/dot_claude/**\n")
        managed = {".claude/a": {"absolute": "/h/.claude/a", "sourceAbsolute": f"{repo}/home/dot_claude/a"},
                   ".zshrc": {"absolute": "/h/.zshrc", "sourceAbsolute": f"{repo}/home/dot_zshrc"}}
        (self.dir / "managed.json").write_text(json.dumps(managed))
        chezmoi = fake(self.dir, "chezmoi", f"""case "$3" in
  managed) cat "{self.dir}/managed.json" ;;
  diff) echo "$@" > "{self.dir}/diff-args"; printf 'diff --git a/.claude/a b/.claude/a\\n-x\\n+y\\n' ;;
esac
""")
        r = ready.check_r1(Path("/h"), repo, chezmoi)
        self.assertEqual((r["status"], r["detail"]), ("FAIL", [".claude/a"]))
        self.assertNotIn(".zshrc", (self.dir / "diff-args").read_text())

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
        (self.dir / "runs").mkdir()
        (self.dir / "runs/2026-11-14.json").write_text(json.dumps({"finished": ts(NOW - timedelta(days=5))}))
        prs = [{"number": 1, "headRefName": "kaizen/x", "createdAt": ts(NOW - timedelta(days=20))},
               {"number": 2, "headRefName": "other", "createdAt": ts(NOW - timedelta(days=20))}]
        gh = fake(self.dir, "gh", f"echo '{json.dumps(prs)}'\n")
        r = ready.check_r5(self.dir, "2026-11-19", NOW, "o/r", gh)
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(len(r["detail"]), 2)
        (self.dir / "runs/2026-11-18.json").write_text(json.dumps({"finished": ts(NOW - timedelta(days=1))}))
        self.assertEqual(ready.check_r5(self.dir, "2026-11-19", NOW, "o/r", fake(self.dir, "gh3", "echo '[]'\n"))
                         ["status"], "PASS")


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
        return {p.relative_to(self.k).as_posix(): p.read_bytes() for p in sorted(self.k.rglob("*")) if p.is_file()}

    def test_run_writes_record_digest_and_status(self):
        summary = self.main()
        self.assertEqual(sorted(self.outputs()), ["digest.md", "runs/2026-11-19.json", "status.json"])
        status = json.loads((self.k / "status.json").read_text())
        self.assertEqual((status["fail"], status["decisions"]), (summary["fail"], summary["decisions"]))
        self.assertGreaterEqual(status["fail"], 2)  # R1 (no chezmoi source) and R2 (job not loaded)
        record = json.loads((self.k / "runs/2026-11-19.json").read_text())
        self.assertEqual(record["cost"], {"claude_usd": 0, "codex_usd": 0})
        self.assertEqual(record["watch"][0]["pre_source"], "live, partial: older transcripts deleted")
        digest = (self.k / "digest.md").read_text()
        for section in ("## 準備状態", "## 取りこぼしと無駄", "## 監視中の変更", "## 判断事項", "## 費用"):
            self.assertIn(section, digest)

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

    def test_sigterm_mid_run_keeps_previous_outputs(self):
        self.main()
        before = self.outputs()
        started = self.dir / "started"
        slow = fake(self.bin, "slow-launchctl", f'touch "{started}"; exec sleep 30\n')
        args = [a if a != self.args[-1] else slow for a in self.args]
        proc = subprocess.Popen([sys.executable, str(KAIZEN / "cycle.py"), *args], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, env={**os.environ, "KAIZEN_HOME": str(self.k)})
        try:
            deadline = time.monotonic() + 60
            while not started.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(started.exists(), "the run did not reach R2")
            proc.send_signal(signal.SIGTERM)
            self.assertEqual(proc.wait(timeout=30), 143)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        self.assertEqual(self.outputs(), before)

    def test_baseline_is_written_once_and_used_by_the_run(self):
        first = self.main("baseline", "#1")
        self.assertTrue(first["written"])
        saved = (self.k / "watch/#1.json").read_bytes()
        self.assertFalse(self.main("baseline", "#1")["written"])
        self.assertEqual((self.k / "watch/#1.json").read_bytes(), saved)
        self.main()
        record = json.loads((self.k / "runs/2026-11-19.json").read_text())
        self.assertEqual(record["watch"][0]["pre_source"], "snapshot")

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
            (self.dir / "status.json").write_text(status if isinstance(status, str) else json.dumps(status))
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
