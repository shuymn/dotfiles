"""The rendered statusline with HOME in a temporary directory."""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "home/dot_claude/executable_statusline.sh.tmpl"
STDIN = json.dumps({"workspace": {"current_dir": "/"}, "model": {"display_name": "M"},
                    "context_window": {"used_percentage": 1}})
PLIST = "Library/LaunchAgents/org.nix-community.home.stack-cycle.plist"


def result(name, findings=0):
    return {"name": name, "status": "pass", "context": "", "error": "", "findings": [{"kind": "x"}] * findings}


@unittest.skipUnless(shutil.which("chezmoi") and shutil.which("jq"), "needs chezmoi and jq")
class Cycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with TEMPLATE.open() as tmpl:
            cls.rendered = subprocess.run(["chezmoi", "--source", str(REPO / "home"), "execute-template"], stdin=tmpl,
                                          capture_output=True, text=True, check=True).stdout

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.script = self.dir / "statusline.sh"
        self.script.write_text(self.rendered)
        self.script.chmod(0o755)
        self.home = self.dir / "home"
        self.state = self.home / ".local/state/stack/cycle"
        self.state.mkdir(parents=True)

    def last(self, value, age_hours=0):
        path = self.state / "last.json"
        path.write_text(value if isinstance(value, str) else json.dumps(value))
        then = time.time() - age_hours * 3600
        os.utime(path, (then, then))

    def error(self):
        (self.state / "last-error").write_text("2026-01-01T00:00:00Z\nobserve: exit 2 without a valid result\n")

    def cycle(self):
        out = subprocess.run([str(self.script)], input=STDIN, capture_output=True, text=True, cwd=self.dir,
                             env={**os.environ, "HOME": str(self.home)}, check=True, timeout=30).stdout
        parts = [p for p in re.sub(r"\x1b\[[0-9;]*m", "", out).strip().split(" | ") if p.startswith("cycle")]
        self.assertLessEqual(len(parts), 1, out)
        return parts[0] if parts else None

    def test_absent_and_not_installed_shows_nothing(self):
        self.assertIsNone(self.cycle())

    def test_absent_with_the_agent_installed_is_never(self):
        (self.home / PLIST).parent.mkdir(parents=True)
        (self.home / PLIST).write_text("<plist/>")
        self.assertEqual(self.cycle(), "cycle never")

    def test_absent_with_last_error_is_failed(self):
        (self.home / PLIST).parent.mkdir(parents=True)
        (self.home / PLIST).write_text("<plist/>")
        self.error()
        self.assertEqual(self.cycle(), "cycle ✗")

    def test_unreadable(self):
        for case, value in {"not JSON": "not json", "status null": "{}", "status not a string": {"status": 1,
                            "results": []}, "results not an array": {"status": "pass", "results": {}}}.items():
            with self.subTest(case):
                self.last(value)
                self.assertEqual(self.cycle(), "cycle ?")

    def test_warn_counts_findings_over_results(self):
        self.last({"stage": "cycle", "status": "warn", "results": [result("observe", 2), result("improve", 1)]})
        self.assertEqual(self.cycle(), "cycle warn 3")

    def test_stale_after_36_hours(self):
        self.last({"stage": "cycle", "status": "pass", "results": [result("observe")]}, age_hours=35)
        self.assertIsNone(self.cycle())
        self.last({"stage": "cycle", "status": "pass", "results": [result("observe")]}, age_hours=37)
        self.assertEqual(self.cycle(), "cycle stale 1d")
        self.last({"stage": "cycle", "status": "warn", "results": [result("observe", 1)]}, age_hours=73)
        self.assertEqual(self.cycle(), "cycle warn 1 stale 3d")

    def test_last_error_with_a_valid_last_json_is_appended(self):
        self.error()
        self.last({"stage": "cycle", "status": "pass", "results": [result("observe")]})
        self.assertEqual(self.cycle(), "cycle ✗")
        self.last({"stage": "cycle", "status": "warn", "results": [result("observe", 1)]}, age_hours=49)
        self.assertEqual(self.cycle(), "cycle warn 1 ✗ stale 2d")

    def test_fresh_pass_shows_nothing(self):
        (self.home / PLIST).parent.mkdir(parents=True)
        (self.home / PLIST).write_text("<plist/>")
        self.last({"stage": "cycle", "status": "pass", "results": [result("observe"), result("improve")]})
        self.assertIsNone(self.cycle())


if __name__ == "__main__":
    unittest.main()
