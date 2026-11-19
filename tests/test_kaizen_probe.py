from contextlib import redirect_stdout
from unittest import mock
import io
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
TEXT = ("A test counts as a regression test only after it has been seen failing with the fix removed and passing with "
        "it restored.")
SESSION = "00000000-0000-4000-8000-000000000301"


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


sys.dont_write_bytecode = True  # importing the scripts must not leave __pycache__ in the checkout
SCORE = load("probe_score", PROBE / "score")
PUBLIC_CHECK = load("public_check", REPO / "scripts/kaizen/public-check")


class TempCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="kaizen-probe-test-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))


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
QUIET = "----------------------------------------------------------------------\nRan 1 test in 0.000s\n\nOK"


def ut_red(cls):
    return RED.replace("PageCountTest", cls)


def ut_green(cls):
    return GREEN.replace("PageCountTest", cls)


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

    def test_red_without_green_is_not_credited(self):
        t = Trace()
        t.bash(CMD, "Exit code 1\n" + RED, is_error=True)
        t.bash(CMD, "Exit code 1\n" + RED, is_error=True)
        self.assertFalse(SCORE.seen_fail2(t.records))

    def test_green_then_red_with_the_fix_removed_is_credited(self):
        t = Trace()
        t.bash(CMD, GREEN)
        t.bash(CMD, "Exit code 1\n" + RED, is_error=True)
        self.assertTrue(SCORE.seen_fail2(t.records))

    def test_printf_of_the_output_is_not_credited(self):
        t = Trace()
        t.bash("printf '%s\\n' " + json.dumps(RED) + " # unittest", RED)
        t.bash("printf '%s\\n' " + json.dumps(GREEN) + " # unittest", GREEN)
        t.call("Write", {"file_path": "/work/paginate/notes.txt", "content": RED + GREEN}, "File created")
        self.assertFalse(SCORE.seen_fail2(t.records))

    def test_same_name_in_another_class_is_not_credited(self):
        t = Trace()
        t.bash("python3 -m unittest -v test_paginate.Case.test_page_count_rounds_up", "Exit code 1\n" + ut_red("Case"),
               is_error=True)
        t.bash("python3 -m unittest -v test_paginate.Other.test_page_count_rounds_up", ut_green("Other"))
        self.assertFalse(SCORE.seen_fail2(t.records))
        t.bash("python3 -m unittest -v test_paginate", ut_green("Case"))
        self.assertTrue(SCORE.seen_fail2(t.records))

    def test_quiet_green_counts_only_for_a_selection_holding_the_test(self):
        for command, credited in [("python3 -m unittest -q test_paginate.py -k test_smoke", False),
                                  ("python3 -m unittest -q test_paginate.Other", False),
                                  ("python3 -m unittest -q", False),
                                  ("cd /work/paginate && python3 -m unittest -q test_paginate", True),
                                  ("python3 -m unittest -q test_paginate.py -k page_count", True),
                                  ("python3 -m unittest -q test_paginate.PageCountTest", True)]:
            with self.subTest(command=command):
                t = Trace()
                t.bash(CMD, "Exit code 1\n" + RED, is_error=True)
                t.bash(command, QUIET)
                self.assertEqual(SCORE.seen_fail2(t.records), credited)

    def test_replayed_logs_are_not_test_runs(self):
        t = Trace()
        t.bash("cat red-unittest.log # unittest", RED)
        t.bash("cat green-unittest.log # unittest", GREEN)
        self.assertFalse(SCORE.seen_fail2(t.records))

    def test_pytest_red_needs_an_assertion_failure(self):
        t = Trace()
        t.bash("python3 -m pytest -q test_paginate.py", "Exit code 1\nFAILED test_paginate.py::test_page_count_rounds_up"
               " - ImportError: cannot import name 'assert_page_count'\n1 failed in 0.02s", is_error=True)
        t.bash("python3 -m pytest -v test_paginate.py", "test_paginate.py::test_page_count_rounds_up PASSED\n"
               "1 passed in 0.01s")
        self.assertFalse(SCORE.seen_fail2(t.records))
        t.bash("python3 -m pytest -q test_paginate.py", "Exit code 1\nFAILED test_paginate.py::test_page_count_rounds_up"
               " - AssertionError: assert 3 == 4\n1 failed in 0.02s", is_error=True)
        self.assertTrue(SCORE.seen_fail2(t.records))

    def test_unittest_red_and_pytest_green_of_one_test_class(self):
        t = Trace()
        t.bash(CMD, "Exit code 1\n" + RED, is_error=True)
        t.bash("python3 -m pytest -v test_paginate.py",
               "test_paginate.py::PageCountTest::test_page_count_rounds_up PASSED\n1 passed in 0.01s")
        self.assertTrue(SCORE.seen_fail2(t.records))

    def test_import_error_is_not_a_red(self):
        t = Trace()
        t.bash(CMD, "Exit code 1\nERROR: test_paginate (unittest.loader._FailedTest.test_paginate)\n"
               "ImportError: cannot import name 'page_count'", is_error=True)
        t.bash(CMD, GREEN)
        self.assertFalse(SCORE.seen_fail2(t.records))


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

    def test_report_holds_only_the_scored_arms(self):
        run = {"complete": True, "t-seen-fail": True, "t-seen-fail2": True, "turns": 1, "final_len": 1, "cost": 0,
               "error": None, "model": "m"}
        saved = {"A": dict(run, arm="A", run="a1", claudeVersion="1"), "B": dict(run, arm="B", run="b1", claudeVersion="2")}
        with mock.patch.object(SCORE, "collect", return_value=["A", "B"]), \
                mock.patch.object(SCORE, "score_run", side_effect=saved.get), redirect_stdout(io.StringIO()):
            report = SCORE.main(["--json"])
        self.assertEqual(([r["arm"] for r in report["runs"]], report["claudeVersion"]), (["B"], ["2"]))


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
            if f.is_file() and f.name != "build.json":
                hits += PUBLIC_CHECK.scan(str(f), f.read_text(), [], [])
        self.assertEqual(hits, [])
        for level in (0, 2):
            b = root / "B" / "evals" / f"worker-L{level}"
            work = self.tmp / f"work-{level}"
            work.mkdir()
            subprocess.run(["bash", str(b / "scaffold.sh")], cwd=work, check=True, timeout=30)
            fixture = PROBE / "fixtures/paginate-bug"
            self.assertEqual({f.name: f.read_bytes() for f in work.iterdir()},
                             {f.name: f.read_bytes() for f in fixture.iterdir()})
            reminder = f"<system-reminder>\n{TEXT}\n</system-reminder>"
            if level == 0:
                self.assertTrue((b / "prompt.md").read_text().split("---\n", 2)[2].lstrip().startswith(reminder))
        hb = [json.loads(l)["message"] for l in (root / "B/evals/worker-L2/history.jsonl").read_text().splitlines()]
        self.assertEqual(hb[0]["content"], [{"type": "text", "text": reminder}])
        self.assertEqual([d.name for d in root.iterdir() if d.is_dir()], ["B"])
        self.assertFalse((root / "B/hooks").exists())

    def test_arms_share_fixture_and_history_without_private_strings(self):
        root = self.build("--filler", str(self.filler()))
        self.check(root)
        self.assertNotIn(self.LEAK, (root / "B/evals/worker-L2/history.jsonl").read_text())

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
