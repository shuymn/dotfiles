from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/kaizen/signals.py"

spec = importlib.util.spec_from_file_location("kaizen_signals", SCRIPT)
signals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signals)


class Transcript:
    """A synthetic subagent transcript: records in order, ten seconds apart from start."""

    ids = itertools.count()

    def __init__(self, cwd, start):
        self.cwd, self.t, self.records = str(cwd), start, []

    def record(self, kind, **fields):
        self.t += timedelta(seconds=10)
        self.records.append({"type": kind, "timestamp": self.t.isoformat().replace("+00:00", "Z"), "cwd": self.cwd,
                             **fields})
        return len(self.records)  # its line number

    def assistant(self, *blocks):
        return self.record("assistant", message={"id": f"msg_{next(self.ids)}", "role": "assistant",
                                                 "content": list(blocks)})

    def tool(self, name, tool_input, output, error=False, result=None):
        tid = f"toolu_{next(self.ids)}"
        self.assistant({"type": "tool_use", "id": tid, "name": name, "input": tool_input})
        block = {"type": "tool_result", "tool_use_id": tid, "content": output}
        if error:
            block["is_error"] = True
        fields = {"toolUseResult": result} if result is not None else {}
        return self.record("user", message={"role": "user", "content": [block]}, **fields)

    def write(self, rel, content, error=False):
        path = f"{self.cwd}/{rel}"
        return self.tool("Write", {"file_path": path, "content": content},
                         "Error" if error else f"File created successfully at: {path}", error)

    def bash(self, command, output):
        return self.tool("Bash", {"command": command}, output)


PY_TEST = "def test_last_page_kept():\n    assert paginate([1, 2, 3], 2)[-1] == [3]\n"
RED = ("FAILED tests/test_paginate.py::test_last_page_kept - AssertionError: assert [] == [3]\n"
       "1 failed in 0.02s")
GREEN = "tests/test_paginate.py::test_last_page_kept PASSED\n1 passed in 0.01s"
UT_TEST = ("import unittest\n\nclass Case(unittest.TestCase):\n    def test_last_page_kept(self):\n        pass\n\n"
           "class Other(unittest.TestCase):\n    def test_last_page_kept(self):\n        pass\n\n"
           "    def test_smoke(self):\n        pass\n")
UT_QUIET = "----------------------------------------------------------------------\nRan 1 test in 0.000s\n\nOK"


def ut_red(cls):
    head = f"test_last_page_kept (test_paginate.{cls}.test_last_page_kept)"
    return (f"{head} ... FAIL\n\n======================================================================\nFAIL: {head}\n"
            "----------------------------------------------------------------------\nTraceback (most recent call last):\n"
            "    self.assertEqual(paginate([1, 2, 3], 2)[-1], [3])\nAssertionError: Lists differ: [] != [3]\n\n"
            "----------------------------------------------------------------------\nRan 1 test in 0.001s\n\n"
            "FAILED (failures=1)")


def ut_green(cls):
    return f"test_last_page_kept (test_paginate.{cls}.test_last_page_kept) ... ok\n\n{UT_QUIET}"


class SignalsCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="signals-test-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        self.projects = self.tmp / "projects"
        self.repo = self.tmp / "work" / "repo"
        (self.repo / ".git").mkdir(parents=True)
        self.now = datetime.now(timezone.utc)
        self.workers = 0

    def transcript(self, days_ago=2):
        return Transcript(self.repo, self.now - timedelta(days=days_ago))

    def save(self, t, agent_type="opus-worker", meta=True, extra=""):
        self.workers += 1
        d = self.projects / "-work-repo" / "session-1" / "subagents"
        d.mkdir(parents=True, exist_ok=True)
        name = f"agent-w{self.workers}"
        if meta:
            (d / f"{name}.meta.json").write_text(json.dumps({"agentType": agent_type, "description": "synthetic"}))
        if t is not None:
            (d / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in t.records) + extra)
        return d / f"{name}.jsonl"

    def run_signal(self, examples=0):
        return signals.regression(self.projects, days=30, examples=examples)

    def assertCounts(self, out, opportunities, counted, ambiguous=0):
        self.assertEqual((out["opportunities"], out["counted"], out["ambiguous"],
                          out["not_counted"]),
                         (opportunities, counted, ambiguous, opportunities - counted - ambiguous))


class RegressionSignal(SignalsCase):
    def test_red_then_green_counts(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", PY_TEST)
        t.bash("pytest tests/test_paginate.py", RED)
        t.bash("pytest tests/test_paginate.py", GREEN)
        self.save(t)
        out = self.run_signal()
        self.assertCounts(out, 1, 1)
        self.assertEqual((out["workers"], out["rate"]), (1, 1.0))

    def test_red_and_green_in_one_result_count_in_either_order(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", PY_TEST)
        t.bash("sh revert-and-rerun.sh", RED + "\n" + GREEN)
        t2 = self.transcript()
        t2.write("tests/test_paginate.py", PY_TEST)
        t2.bash("sh rerun-and-revert.sh", GREEN + "\n" + RED)
        self.save(t)
        self.save(t2)
        self.assertCounts(self.run_signal(), 2, 2)

    def test_import_error_red_does_not_count(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", PY_TEST)
        t.bash("pytest tests/test_paginate.py",
               "E   ImportError: cannot import name 'paginate'\n"
               "FAILED tests/test_paginate.py::test_last_page_kept - ImportError\n1 failed in 0.02s")
        t.bash("pytest tests/test_paginate.py", GREEN)
        self.save(t)
        out = self.run_signal(examples=3)
        self.assertCounts(out, 1, 0)
        self.assertEqual(out["examples"]["not_counted"][0]["reason"], "no red for an intended reason after the write")

    def test_green_only_does_not_count(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", PY_TEST)
        t.bash("pytest tests/test_paginate.py", GREEN)
        self.save(t)
        self.assertCounts(self.run_signal(), 1, 0)

    def test_red_of_another_test_then_green_is_ambiguous(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", PY_TEST)
        t.bash("pytest tests/test_other.py",
               "FAILED tests/test_other.py::test_other - AssertionError: assert 1 == 2\n1 failed in 0.02s")
        t.bash("pytest tests/test_other.py", "tests/test_other.py::test_other PASSED\n1 passed in 0.01s")
        self.save(t)
        self.assertCounts(self.run_signal(), 1, 0, ambiguous=1)

    def test_clean_pass_after_cd_to_the_root_is_not_attributed(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", PY_TEST)
        t.bash("pytest tests/test_paginate.py", RED)
        t.bash(f"cd {self.repo} && pytest -q", "3 passed in 0.03s")
        self.save(t)
        self.assertCounts(self.run_signal(), 1, 0, ambiguous=1)

    def test_same_name_in_another_class_is_not_the_same_test(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", UT_TEST)
        t.bash("python3 -m unittest -v test_paginate.Case.test_last_page_kept", ut_red("Case"))
        t.bash("python3 -m unittest -v test_paginate.Other.test_last_page_kept", ut_green("Other"))
        self.save(t)
        self.assertCounts(self.run_signal(), 1, 0, ambiguous=1)

    def test_same_class_red_and_green_count(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", UT_TEST)
        t.bash("python3 -m unittest -v test_paginate.Case.test_last_page_kept", ut_red("Case"))
        t.bash("python3 -m unittest -v test_paginate", ut_green("Case") + "\n" + ut_green("Other"))
        t2 = self.transcript()
        t2.write("tests/test_paginate.py", UT_TEST)
        t2.bash("cd tests && python3 -m unittest -v test_paginate.Case", ut_red("Case"))
        t2.bash("cd tests && python3 -m unittest -q test_paginate.Case", UT_QUIET)
        self.save(t)
        self.save(t2)
        self.assertCounts(self.run_signal(), 2, 2)

    def test_quiet_green_of_another_selection_is_not_attributed(self):
        for command in ("python3 -m unittest -q test_paginate.py -k test_smoke",
                        "python3 -m unittest -q test_paginate.Other", "pytest -q tests/test_paginate.py::test_smoke",
                        "pytest -q tests/test_paginate.py -k 'not last_page'"):
            with self.subTest(command=command):
                t = self.transcript()
                t.write("tests/test_paginate.py", UT_TEST)
                t.bash("python3 -m unittest -v test_paginate.Case.test_last_page_kept", ut_red("Case"))
                t.bash(command, UT_QUIET if "unittest" in command else "1 passed in 0.01s")
                self.projects = self.tmp / f"projects-{command}"
                self.save(t)
                self.assertCounts(self.run_signal(), 1, 0, ambiguous=1)

    def test_quiet_green_of_a_selection_holding_the_test_counts(self):
        for command in ("python3 -m unittest -q test_paginate.py -k last_page",
                        "pytest -q tests/test_paginate.py -k 'last_page and not smoke'"):
            with self.subTest(command=command):
                t = self.transcript()
                t.write("tests/test_paginate.py", UT_TEST)
                t.bash("python3 -m unittest -v test_paginate.Case.test_last_page_kept", ut_red("Case"))
                t.bash(command, UT_QUIET if "unittest" in command else "1 passed in 0.01s")
                self.projects = self.tmp / f"projects-{command}"
                self.save(t)
                self.assertCounts(self.run_signal(), 1, 1)

    def test_replayed_logs_are_not_test_runs(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", UT_TEST)
        t.bash("cat red-unittest.log # unittest", ut_red("Case"))
        t.bash("cat green-unittest.log # unittest", ut_green("Case") + "\n" + UT_QUIET)
        self.save(t)
        self.assertCounts(self.run_signal(), 1, 0)

    def test_clean_pass_of_a_directory_above_the_test_is_attributed(self):
        t = self.transcript()
        t.write("tools/ledger/tests/test_paginate.py", PY_TEST)
        t.bash("pytest -q tools/ledger", RED)
        t.bash("pytest -q tools/ledger/ | tail -1", "3 passed in 0.03s")
        self.save(t)
        self.assertCounts(self.run_signal(), 1, 1)

    def test_vitest_and_go_shapes(self):
        t = self.transcript()
        t.write("test/page.test.ts", "it('keeps the last page', () => {\n  expect(page(3)).toEqual([3])\n})\n")
        t.bash("pnpm vitest run test/page.test.ts",
               " × keeps the last page 3ms\nAssertionError: expected [] to deeply equal [ 3 ]\n Tests  1 failed (1)")
        t.bash("pnpm vitest run test/page.test.ts", " ✓ test/page.test.ts (1 test) 2ms\n Test Files  1 passed (1)")
        g = self.transcript()
        g.write("paginate/page_test.go", "func TestLastPage(t *testing.T) {\n}\n")
        g.bash("go test ./...", "--- FAIL: TestLastPage (0.00s)\n    page_test.go:9: got 2 want 3\nFAIL\n")
        g.bash("go test ./...", "ok  \texample.com/m/paginate\t0.10s\n")
        self.save(t)
        self.save(g)
        self.assertCounts(self.run_signal(), 2, 2)

    def test_edit_without_a_test_name_uses_the_enclosing_test(self):
        t = self.transcript()
        original = "def test_first():\n    assert True\n\ndef test_last_page_kept():\n    assert page() == 1\n"
        path = f"{self.repo}/tests/test_paginate.py"
        t.tool("Edit", {"file_path": path, "old_string": "assert page() == 1", "new_string": "assert page() == [3]"},
               "updated", result={"filePath": path, "originalFile": original})
        t.bash("pytest tests/test_paginate.py", RED)
        t.bash("pytest -k test_last_page_kept", "1 passed in 0.01s")
        self.save(t)
        self.assertCounts(self.run_signal(), 1, 1)

    def test_failed_write_is_no_opportunity(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", PY_TEST, error=True)
        t.bash("pytest tests/test_paginate.py", RED)
        t.bash("pytest tests/test_paginate.py", GREEN)
        self.save(t)
        out = self.run_signal()
        self.assertCounts(out, 0, 0)
        self.assertEqual((out["workers"], out["rate"]), (1, None))

    def test_non_test_file_is_no_opportunity(self):
        t = self.transcript()
        t.write("paginate.py", PY_TEST)
        t.bash("pytest", RED)
        t.bash("pytest", GREEN)
        self.save(t)
        self.assertCounts(self.run_signal(), 0, 0)

    def test_non_worker_meta_is_not_read(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", PY_TEST)
        t.bash("pytest tests/test_paginate.py", RED)
        t.bash("pytest tests/test_paginate.py", GREEN)
        self.save(t, agent_type="general-purpose")
        out = self.run_signal()
        self.assertEqual(out["workers"], 0)
        self.assertCounts(out, 0, 0)

    def test_events_outside_the_window_are_ignored(self):
        old = self.transcript(days_ago=40)
        old.write("tests/test_paginate.py", PY_TEST)
        old.bash("pytest tests/test_paginate.py", RED)
        old.bash("pytest tests/test_paginate.py", GREEN)
        self.save(old)
        straddling = self.transcript(days_ago=40)
        straddling.write("tests/test_paginate.py", PY_TEST)
        straddling.t = self.now - timedelta(days=1)
        straddling.bash("pytest tests/test_paginate.py", RED)
        straddling.bash("pytest tests/test_paginate.py", GREEN)
        self.save(straddling)
        out = self.run_signal()
        self.assertEqual(out["workers"], 1)
        self.assertCounts(out, 0, 0)

    def test_one_opportunity_per_worker(self):
        a = self.transcript()
        a.write("tests/test_paginate.py", PY_TEST)
        a.write("tests/test_more.py", PY_TEST)
        b = self.transcript()
        b.write("tests/test_paginate.py", PY_TEST)
        c = self.transcript()
        c.write("README.md", "x")
        self.save(a)
        self.save(b)
        self.save(c)
        out = self.run_signal()
        self.assertNotIn("deliveries", out)
        self.assertEqual((out["workers"], out["opportunities"]), (3, 2))

    def test_missing_and_unreadable_traces(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", PY_TEST)
        self.save(t, extra="{not json\n")
        self.save(None)
        d = self.projects / "-work-repo" / "session-1" / "subagents"
        (d / "agent-bad.meta.json").write_text("{")
        out = self.run_signal()
        self.assertEqual(out["traces"], {"missing": 1, "unreadable": 0, "unreadable_meta": 1, "bad_lines": 1})
        self.assertEqual((out["workers"], out["opportunities"]), (1, 1))

    def test_harm_medians_split_by_opportunity(self):
        t = self.transcript()
        t.write("tests/test_paginate.py", PY_TEST)
        t.assistant({"type": "text", "text": "x" * 40})
        t.tool("SubagentHandback", {"message": "y" * 10}, "delivered")
        u = self.transcript()
        u.assistant({"type": "text", "text": "z" * 7})
        self.save(t)
        self.save(u)
        harm = self.run_signal()["harm"]
        self.assertEqual(harm["with_opportunity"], {"workers": 1, "median_turns": 3, "median_report_chars": 10})
        self.assertEqual(harm["without_opportunity"], {"workers": 1, "median_turns": 1, "median_report_chars": 7})


class Matcher(unittest.TestCase):
    """A test-file write is an opportunity by path below the root of cwd, by write tool only."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="signals-matcher-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        self.repo = self.tmp / "work" / "repo"
        (self.repo / ".git").mkdir(parents=True)

    def hit(self, path, cwd=None, tool="Write"):
        path = Path(path) if os.path.isabs(path) else self.repo / path
        return signals.is_opportunity(signals.UNIT, tool, {"file_path": str(path)}, str(cwd or self.repo))

    def test_test_file_names(self):
        for f in ["pkg/a_test.go", "web/a.test.ts", "web/a.test.tsx", "web/a.test.js", "web/a.spec.ts", "web/a.spec.js",
                  "py/test_a.py", "py/a_test.py", "tests/a.rs", "crates/x/tests/a.rs"]:
            for tool in ("Edit", "Write", "MultiEdit"):
                with self.subTest(file=f, tool=tool):
                    self.assertTrue(self.hit(f, tool=tool))
        self.assertFalse(self.hit("pkg/a_test.go", tool="Bash"))
        self.assertFalse(signals.is_opportunity(signals.UNIT, "Write", {"file_path": "pkg/a_test.go"}, str(self.repo)))

    def test_other_paths(self):
        outside = self.tmp / "work" / "elsewhere"
        outside.mkdir()
        (self.repo / "link").symlink_to(outside, target_is_directory=True)
        for f in ["pkg/foo.go", "web/x.spec.tsx", "web/a.test.jsx", "tests/common/mod.rs", "src/a.rs", "tests/a.rs.bak",
                  "pkg/A_TEST.GO", str(outside / "a_test.go"), str(outside / "tests" / "a.rs"),
                  str(self.repo / "link" / "test_a.py")]:
            with self.subTest(file=f):
                self.assertFalse(self.hit(f))

    def test_root_is_the_nearest_git_ancestor_else_cwd(self):
        repo = self.tmp / "tests" / "repo"
        (repo / ".git").mkdir(parents=True)
        self.assertFalse(self.hit(str(repo / "a.rs"), cwd=repo))
        self.assertTrue(self.hit(str(repo / "tests" / "a.rs"), cwd=repo))
        wt = self.tmp / "tests" / "wt"
        (wt / "sub").mkdir(parents=True)
        (wt / ".git").write_text("gitdir: elsewhere\n")
        self.assertFalse(self.hit(str(self.tmp / "tests" / "a_test.go"), cwd=wt / "sub"))
        self.assertTrue(self.hit(str(wt / "tests" / "a.rs"), cwd=wt / "sub"))
        plain = self.tmp / "plain"
        self.assertFalse(self.hit(str(self.tmp / "other" / "test_a.py"), cwd=plain))
        self.assertTrue(self.hit(str(plain / "test_a.py"), cwd=plain))


class Cli(SignalsCase):
    def cli(self, *args):
        p = subprocess.run([sys.executable, str(SCRIPT), "regression", "--projects", str(self.projects), *args],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual((p.returncode, p.stderr), (0, ""))
        return p.stdout

    def test_examples_name_transcript_lines(self):
        t = self.transcript()
        write = t.write("tests/test_paginate.py", PY_TEST)
        red = t.bash("pytest tests/test_paginate.py", RED)
        green = t.bash("pytest tests/test_paginate.py", GREEN)
        path = self.save(t)
        out = json.loads(self.cli("--days", "30", "--json", "--examples", "3"))
        self.assertEqual(out["examples"]["counted"], [{
            "write": f"{path}:{write}: wrote {self.repo}/tests/test_paginate.py",
            "red": f"{path}:{red}: FAILED tests/test_paginate.py::test_last_page_kept - AssertionError: assert [] == [3]",
            "green": f"{path}:{green}: tests/test_paginate.py::test_last_page_kept PASSED",
            "test": "test_last_page_kept"}])
        self.assertEqual((out["examples"]["not_counted"], out["examples"]["ambiguous"]), ([], []))

    def test_text_output_states_a_zero_denominator(self):
        self.projects.mkdir()
        self.assertIn("0 opportunities, 0 counted, 0 ambiguous, 0 not counted; rate n/a (no opportunities)",
                      self.cli())


if __name__ == "__main__":
    unittest.main()
