from pathlib import Path
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
PROBE = REPO / "scripts/kaizen/probe"
HOOK = REPO / "home/dot_claude/hooks/executable_orchestration-context.py"
SHIM = PROBE / "shim.py"
TEXT = ("A test counts as a regression test only after it has been seen failing with the fix removed and passing with "
        "it restored.")
EXPECTED = json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": TEXT}})
SESSION = "00000000-0000-4000-8000-000000000301"


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


sys.dont_write_bytecode = True  # importing the scripts must not leave __pycache__ in the checkout
RUN = load("probe_run", PROBE / "run")
SCORE = load("probe_score", PROBE / "score")
PUBLIC_CHECK = load("public_check", REPO / "scripts/kaizen/public-check")


class TempCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="kaizen-probe-test-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))


class ShimTest(TempCase):
    """Arm A: the shim plus the real hook deliver the unit once per run."""

    def setUp(self):
        super().setUp()
        self.cwd = self.tmp / "work"
        self.cwd.mkdir()

    def write_event(self, name):
        path = self.cwd / name
        path.write_text("x\n")
        return {"hook_event_name": "PostToolUse", "session_id": SESSION, "cwd": str(self.cwd), "tool_name": "Write",
                "tool_input": {"file_path": str(path)}, "tool_response": {"filePath": str(path)}}

    def shim(self, event, env):
        p = subprocess.run([sys.executable, str(SHIM), str(HOOK)], input=json.dumps(event), capture_output=True,
                           text=True, env=env, timeout=30)
        self.assertEqual((p.returncode, p.stderr), (0, ""))
        return p.stdout

    def env(self, name, **extra):
        base = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.tmp / name / "home"),
                "TMPDIR": str(self.tmp / name / "tmp")}
        for d in (base["HOME"], base["TMPDIR"]):
            os.makedirs(d, exist_ok=True)
        return {**base, **extra}

    def test_first_test_write_emits_and_second_is_silent(self):
        env = self.env("one")
        self.assertEqual(self.shim(self.write_event("test_paginate.py"), env), EXPECTED)
        self.assertEqual(self.shim(self.write_event("test_more.py"), env), "")

    def test_non_test_write_is_silent(self):
        self.assertEqual(self.shim(self.write_event("paginate.py"), self.env("one")), "")

    def test_runs_sharing_a_session_each_emit_once(self):
        outputs, logs = {}, {}
        for name in ("run-a", "run-b"):
            env = RUN.run_env(self.tmp / name, {"PATH": os.environ.get("PATH", "")})
            for d in (env["HOME"], env["TMPDIR"]):
                os.makedirs(d, exist_ok=True)
            outputs[name] = [self.shim(self.write_event(f), env) for f in ("test_paginate.py", "test_more.py")]
            logs[name] = Path(env["EVAL_KAIZEN_PROBE_TMPDIR"]) / "shim.log"
        self.assertEqual(outputs, {"run-a": [EXPECTED, ""], "run-b": [EXPECTED, ""]})
        for log in logs.values():
            self.assertEqual([json.loads(l)["emitted"] for l in log.read_text().splitlines()], [True, False])

    def test_probe_state_dir_wins_over_a_shared_tmpdir(self):
        """If the eval does not pass TMPDIR on to hooks, EVAL_KAIZEN_PROBE_TMPDIR still separates the runs."""
        shared = self.env("shared")
        for name in ("run-a", "run-b"):
            state = self.tmp / name
            state.mkdir()
            env = {**shared, "EVAL_KAIZEN_PROBE_TMPDIR": str(state)}
            self.assertEqual([self.shim(self.write_event(f), env) for f in ("test_a.py", "test_b.py")], [EXPECTED, ""])


class Trace:
    """A stream-json trace like the eval keeps: init, then assistant tool_use and user tool_result records."""

    def __init__(self, cwd="/work/paginate"):
        self.cwd, self.records, self.n = cwd, [{"type": "system", "subtype": "init", "cwd": cwd, "session_id": SESSION,
                                                "model": "claude-opus-5-5"}], 0

    def call(self, name, inp, output, is_error=False):
        self.n += 1
        tid = f"toolu_{self.n:03d}"
        self.records.append({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
        self.records.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tid, "content": output, "is_error": is_error}]}})
        return tid

    def bash(self, command, output, is_error=False):
        return self.call("Bash", {"command": command}, output, is_error)

    def write(self, name, ok=True):
        path = f"{self.cwd}/{name}"
        return self.call("Write", {"file_path": path, "content": "x"},
                         f"File created successfully at: {path}" if ok else "Error writing file", not ok)

    def say(self, text):
        self.records.append({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": text}]}})


RED = ("test_page_count_rounds_up (test_paginate.PageCountTest.test_page_count_rounds_up) ... FAIL\n\n"
       "======================================================================\n"
       "FAIL: test_page_count_rounds_up (test_paginate.PageCountTest.test_page_count_rounds_up)\n"
       "----------------------------------------------------------------------\n"
       "Traceback (most recent call last):\n  File \"test_paginate.py\", line 8, in test_page_count_rounds_up\n"
       "    self.assertEqual(page_count(10, 3), 4)\nAssertionError: 3 != 4\n\n"
       "----------------------------------------------------------------------\nRan 1 test in 0.001s\n\n"
       "FAILED (failures=1)")
GREEN = ("test_page_count_rounds_up (test_paginate.PageCountTest.test_page_count_rounds_up) ... ok\n\n"
         "----------------------------------------------------------------------\nRan 1 test in 0.000s\n\nOK")
CMD = "/usr/bin/python3 -m unittest -v test_paginate"


class SeenFailTest(unittest.TestCase):
    def test_credits_red_then_green_of_the_pagination_test(self):
        t = Trace()
        t.write("test_paginate.py")
        t.bash(CMD, "Exit code 1\n" + RED, is_error=True)
        t.bash(CMD, GREEN)
        self.assertTrue(SCORE.seen_fail2(t.records))

    def test_unrelated_failure_is_not_credited(self):
        t = Trace()
        t.bash(CMD, "Exit code 1\n" + RED.replace("test_page_count_rounds_up", "test_unrelated")
               .replace("page_count(10, 3), 4", "parse('a'), 'b'").replace("3 != 4", "'a' != 'b'"), is_error=True)
        t.bash(CMD, GREEN.replace("test_page_count_rounds_up", "test_unrelated"))
        self.assertFalse(SCORE.seen_fail2(t.records))

    def test_red_without_later_green_is_not_credited(self):
        t = Trace()
        t.bash(CMD, GREEN)
        t.bash(CMD, "Exit code 1\n" + RED, is_error=True)
        self.assertFalse(SCORE.seen_fail2(t.records))

    def test_printf_of_the_output_is_not_credited(self):
        t = Trace()
        t.bash("printf '%s\\n' " + json.dumps(RED) + " # unittest", RED)
        t.bash("printf '%s\\n' " + json.dumps(GREEN) + " # unittest", GREEN)
        t.call("Write", {"file_path": "/work/paginate/notes.txt", "content": RED + GREEN}, "File created")
        self.assertFalse(SCORE.seen_fail2(t.records))

    def test_import_error_is_not_a_red(self):
        t = Trace()
        t.bash(CMD, "Exit code 1\nERROR: test_paginate (unittest.loader._FailedTest.test_paginate)\n"
               "ImportError: cannot import name 'page_count'", is_error=True)
        t.bash(CMD, GREEN)
        self.assertFalse(SCORE.seen_fail2(t.records))


class DeliveredTest(unittest.TestCase):
    def setUp(self):
        self.unit, self.hook = SCORE.unit_of(), SCORE.load_hook()

    def attachment(self, tid):
        return {"type": "attachment", "attachment": {"type": "hook_additional_context", "content": [TEXT],
                                                     "hookName": "PostToolUse:Write", "toolUseID": tid,
                                                     "hookEvent": "PostToolUse"}}

    def test_hook_record_tied_to_the_first_eligible_write(self):
        t = Trace()
        t.write("paginate.py")
        tid = t.write("test_paginate.py")
        transcript = t.records[1:] + [self.attachment(tid)]
        got = SCORE.delivery(t.records, [transcript], self.unit, self.hook)
        self.assertEqual(got, {"delivered": True, "deliveries": 1, "first_write": "test_paginate.py",
                               "on_first_write": True})

    def test_echo_of_the_sentence_is_not_a_delivery(self):
        t = Trace()
        t.write("test_paginate.py")
        t.say(TEXT)
        t.bash(f"echo '{TEXT}'", TEXT)
        got = SCORE.delivery(t.records, [t.records[1:]], self.unit, self.hook)
        self.assertEqual((got["delivered"], got["first_write"]), (False, "test_paginate.py"))

    def test_record_tied_to_a_failed_or_ineligible_write_does_not_count(self):
        t = Trace()
        failed = t.write("test_paginate.py", ok=False)
        other = t.write("paginate.py")
        transcript = t.records[1:] + [self.attachment(failed), self.attachment(other)]
        self.assertFalse(SCORE.delivery(t.records, [transcript], self.unit, self.hook)["delivered"])


class VerdictTest(unittest.TestCase):
    def rows(self, arm, passed, complete=6):
        return [{"arm": arm, "complete": i < complete, "t-seen-fail2": i < passed} for i in range(6)]

    def test_win_rule(self):
        cases = [((5, 2), "A wins"), ((2, 6), "B wins"), ((5, 5), "no winner"), ((4, 1), "no winner")]
        for (a, b), outcome in cases:
            with self.subTest(a=a, b=b):
                self.assertEqual(SCORE.verdict(self.rows("A", a) + self.rows("B", b), ["A", "B"], 6)[1], outcome)

    def test_incomplete_arm_is_inconclusive(self):
        outcome = SCORE.verdict(self.rows("A", 5, complete=5) + self.rows("B", 0), ["A", "B"], 6)[1]
        self.assertTrue(outcome.startswith("inconclusive"), outcome)


class BuildTest(TempCase):
    LEAK = "/" + "Users/someone/private"  # split so the committed line is not a local path itself

    def build(self, *args):
        home = self.tmp / "home"
        home.mkdir(exist_ok=True)
        p = subprocess.run([sys.executable, str(PROBE / "build"), "--out", str(self.tmp / "out"), *args],
                           capture_output=True, text=True, timeout=120,
                           env={"PATH": os.environ.get("PATH", ""), "HOME": str(home)})
        self.assertEqual(p.returncode, 0, p.stderr)
        return self.tmp / "out" / "build"

    def filler(self):
        items = [{"sha": f"{i:040x}", "title": f"Change number {i}", "body": "Details of the change.",
                  "diff": f"Change number {i}\n file.txt | 1 +\n+line {i}\n"} for i in range(11)]
        items[0]["body"] = f"See {self.LEAK}/notes.md"
        path = self.tmp / "filler.json"
        path.write_text(json.dumps(items))
        return path

    def check(self, root):
        hits = []
        for f in sorted(root.rglob("*")):
            if f.is_file() and f.parent.name != "hooks" and f.name not in ("shim.py", "build.json"):
                hits += PUBLIC_CHECK.scan(str(f), f.read_text(), [], [])
        self.assertEqual(hits, [])
        for level in (0, 2):
            a, b = (root / arm / "evals" / f"worker-L{level}" for arm in ("A", "B"))
            self.assertEqual((a / "scaffold.sh").read_bytes(), (b / "scaffold.sh").read_bytes())
            work = self.tmp / f"work-{level}"
            work.mkdir()
            subprocess.run(["bash", str(a / "scaffold.sh")], cwd=work, check=True, timeout=30)
            fixture = PROBE / "fixtures/paginate-bug"
            self.assertEqual({f.name: f.read_bytes() for f in work.iterdir()},
                             {f.name: f.read_bytes() for f in fixture.iterdir()})
            self.assertNotIn(TEXT, (a / "prompt.md").read_text())
            self.assertIn(TEXT, (b / "prompt.md").read_text() if level == 0 else (b / "history.jsonl").read_text())
        ha, hb = ([{k: v for k, v in json.loads(l)["message"].items() if k != "id"}
                   for l in (root / arm / "evals/worker-L2/history.jsonl").read_text().splitlines()] for arm in "AB")
        self.assertEqual(hb[0]["content"], [{"type": "text", "text": f"<system-reminder>\n{TEXT}\n</system-reminder>"}])
        self.assertEqual(ha, hb[1:])
        self.assertNotIn(TEXT, json.dumps(ha))
        hooks = json.loads((root / "A/hooks/hooks.json").read_text())["hooks"]["PostToolUse"][0]
        self.assertEqual(hooks["matcher"], "Edit|Write|MultiEdit")
        self.assertIn(str(HOOK), hooks["hooks"][0]["command"])
        self.assertFalse((root / "B/hooks").exists())

    def test_arms_share_fixture_and_history_without_private_strings(self):
        root = self.build("--filler", str(self.filler()))
        self.check(root)
        self.assertNotIn(self.LEAK, (root / "A/evals/worker-L2/history.jsonl").read_text())

    def test_real_merge_filler_is_public(self):
        shallow = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--is-shallow-repository"],
                                 capture_output=True, text=True).stdout.strip()
        rev = load("probe_build", PROBE / "build").DEFAULT_REV
        present = subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", f"{rev}^{{commit}}"]).returncode == 0
        if shallow != "false" or not present:
            self.skipTest("needs the full history (CI checks out one commit)")
        self.check(self.build())


if __name__ == "__main__":
    unittest.main()
