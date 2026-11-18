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
TEXT = ("A test counts as a regression test only after it has been seen failing with the fix removed and passing with "
        "it restored.")

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

    def attach(self, text):
        return self.record("attachment", attachment={"type": "hook_additional_context", "content": [text],
                                                     "hookEvent": "PostToolUse"})


PY_TEST = "def test_last_page_kept():\n    assert paginate([1, 2, 3], 2)[-1] == [3]\n"
RED = ("FAILED tests/test_paginate.py::test_last_page_kept - AssertionError: assert [] == [3]\n"
       "1 failed in 0.02s")
GREEN = "tests/test_paginate.py::test_last_page_kept PASSED\n1 passed in 0.01s"


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
        self.assertEqual((out["workers"], out["rate"], out["deliveries"]["rate"]), (1, None, None))

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

    def test_deliveries_count_attachments_with_the_unit_text(self):
        a = self.transcript()
        a.write("tests/test_paginate.py", PY_TEST)
        a.attach(TEXT)
        a.attach("Some other hook context.")
        a.write("tests/test_more.py", PY_TEST)
        a.attach(TEXT)
        b = self.transcript()
        b.write("tests/test_paginate.py", PY_TEST)
        c = self.transcript()
        c.write("README.md", "x")
        self.save(a)
        self.save(b)
        self.save(c)
        out = self.run_signal()
        self.assertEqual(out["deliveries"], {"attachments": 2, "workers": 1, "opportunities_delivered": 1,
                                             "opportunities_missed": 1, "duplicated": 1, "rate": 0.5})
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
