import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/dot_local/private_bin/executable_capsule-chezmoi-drift"


class CapsuleChezmoiDriftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.work = self.root / "dotfiles"
        (self.work / "sub").mkdir(parents=True)
        self.outside = self.root / "outside"
        self.outside.mkdir()
        self.cache = self.root / "cache/capsule/chezmoi-status"
        # Keep PATH to this directory so the real chezmoi never runs.
        for command in ("find", "mkdir", "rmdir", "mv", "rm", "sleep"):
            path = shutil.which(command)
            self.assertIsNotNone(path, f"{command} is required")
            (self.bin / command).symlink_to(path)
        self.env = {
            "PATH": str(self.bin),
            "HOME": str(self.root),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "MOCK_ROOT": str(self.work),
            "MOCK_STATUS": " M .zshrc\n A .local/bin/tool\n",
        }
        self.mock("chezmoi", 'case "$1" in\n'
                  'execute-template) printf "%s" "$MOCK_ROOT" ;;\n'
                  'status) sleep "${MOCK_DELAY:-0}"; printf "%s" "$MOCK_STATUS"; '
                  'exit "${MOCK_STATUS_EXIT:-0}" ;;\n'
                  'source-path) case "$2" in *modified) printf "/src/modify_x" ;; '
                  '*) printf "/src/x" ;; esac ;;\n'
                  '*) exit 2 ;;\nesac')

    def mock(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def run_helper(self, cwd=None):
        return subprocess.run(["/bin/sh", str(SCRIPT)], env=self.env, cwd=cwd or self.work,
                              capture_output=True, text=True, timeout=5)

    def wait_for_refresh(self):
        lock = self.cache.with_name("chezmoi-status.lock")
        for _ in range(100):
            if self.cache.parent.exists() and not lock.exists():
                return
            time.sleep(0.05)
        self.fail("refresh did not finish")

    def test_reports_previous_refresh_inside_working_tree(self):
        first = self.run_helper()
        self.assertNotEqual(first.returncode, 0)
        self.assertEqual(first.stdout, "")
        self.wait_for_refresh()
        for cwd in (self.work, self.work / "sub"):
            with self.subTest(cwd=cwd):
                result = self.run_helper(cwd)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "!+\n")
                self.wait_for_refresh()

    def test_maps_status_to_git_indicators(self):
        cases = {
            " A a\n M b\n": "!+\n",
            "MM a\n D b\n R c\n": "=✘!\n",
            " M a\nDA b\n": "=!\n",
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                self.cache.parent.mkdir(parents=True, exist_ok=True)
                self.cache.write_text(status)
                self.env["MOCK_STATUS"] = status
                result = self.run_helper()
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, expected)
                self.wait_for_refresh()

    def test_modify_script_target_is_not_a_conflict(self):
        # Apply overwrites modify_ targets without asking, unlike other edited targets.
        self.env["MOCK_STATUS"] = "MM .modified\n"
        self.run_helper()
        self.wait_for_refresh()
        self.assertEqual(self.run_helper().stdout, "!\n")
        self.wait_for_refresh()
        self.env["MOCK_STATUS"] = "MM .edited\n"
        self.run_helper()
        self.wait_for_refresh()
        self.assertEqual(self.run_helper().stdout, "=\n")
        self.wait_for_refresh()

    def test_clean_or_failed_status_is_hidden(self):
        # "M " means the target already matches the source, so apply changes nothing.
        for env in ({"MOCK_STATUS": ""}, {"MOCK_STATUS": "M  .zshrc\n"}, {"MOCK_STATUS_EXIT": "1"}):
            with self.subTest(env=env):
                self.cache.parent.mkdir(parents=True, exist_ok=True)
                self.cache.write_text(" M .zshrc\n")
                self.env.update(env)
                self.run_helper()
                self.wait_for_refresh()
                result = self.run_helper()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.wait_for_refresh()

    def test_outside_working_tree_is_hidden_without_refresh(self):
        result = self.run_helper(self.outside)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertFalse(self.cache.parent.exists())

    def test_refresh_survives_process_group_cleanup(self):
        # Capsule kills the command's process group once the command finishes.
        self.env["MOCK_DELAY"] = "0.3"
        process = subprocess.Popen(["/bin/sh", str(SCRIPT)], env=self.env, cwd=self.work,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True)
        process.wait(timeout=5)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.wait_for_refresh()
        self.assertEqual(self.cache.read_text(), self.env["MOCK_STATUS"])

    def test_concurrent_refresh_is_skipped(self):
        lock = self.cache.with_name("chezmoi-status.lock")
        lock.mkdir(parents=True)
        self.run_helper()
        time.sleep(0.2)
        self.assertTrue(lock.exists())
        self.assertFalse(self.cache.exists())


if __name__ == "__main__":
    unittest.main()
