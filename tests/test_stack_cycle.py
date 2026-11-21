"""scripts/stack-cycle with a fake stack and chezmoi on PATH and HOME in a temporary directory."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/stack-cycle"
DISPATCH = None
OLD_LAST = b'{"stage":"cycle","status":"pass","results":[],"skipped":[],"old":true}\n'
OLD_ERROR = b"2026-01-01T00:00:00Z\nold failure\n"
DATE = shutil.which("date", path="/usr/bin:/bin")


def setUpModule():
    # One executable that every fake links to: macOS scans each new executable on its first run, which takes seconds
    global DISPATCH
    DISPATCH = Path(tempfile.mkdtemp()) / "dispatch"
    DISPATCH.write_text('#!/bin/sh\n. "$0.body"\n')
    DISPATCH.chmod(0o755)


def tearDownModule():
    shutil.rmtree(DISPATCH.parent)


def response(name, status="pass", **result):
    return {"stage": "cycle", "status": status, "skipped": [],
            "results": [{"name": name, "status": status, "context": f"{name} ran", "error": "", "findings": [],
                         **result}]}


def body(output, code=0, fresh=False):
    """A fake stage: optionally rewrite latest.json with a window ending now, print output, exit code."""
    lines = []
    if fresh:
        lines.append('printf \'{"version":1,"window":{"since":"2000-01-01T00:00:00Z","until":"%s"}}\' '
                     '"$(' + DATE + ' -u +%Y-%m-%dT%H:%M:%SZ)" >"$HOME/.local/state/stack/observe/latest.json"')
    lines.append(f"printf '%s' {sh_quote(output)}")
    lines.append(f"exit {code}")
    return "\n".join(lines) + "\n"


def sh_quote(text):
    return "'" + text.replace("'", "'\\''") + "'"


def dump(value):
    return value if isinstance(value, str) else json.dumps(value)


INVALID = {
    "non-zero exit with valid JSON": lambda n: (dump(response(n)), 1),
    "empty output": lambda n: ("", 0),
    "two JSON objects": lambda n: (dump(response(n)) + dump(response(n)), 0),
    "empty object": lambda n: ("{}", 0),
    "stage not cycle": lambda n: (dump({**response(n), "stage": "check"}), 0),
    "status block": lambda n: (dump({**response(n), "status": "block"}), 0),
    "only in skipped": lambda n: (dump({"stage": "cycle", "status": "pass", "results": [],
                                        "skipped": [{"name": n, "reason": "not found"}]}), 0),
    "synthetic error": lambda n: (dump(response(n, status="warn", error="extension crashed")), 0),
    "result status outside pass/warn": lambda n: (dump({**response(n), "results": [
        {**response(n)["results"][0], "status": "fail"}]}), 0),
    "findings not an array": lambda n: (dump(response(n, findings={})), 0),
    "result of the other extension": lambda n: (dump(response("improve" if n == "observe" else "observe")), 0),
}


@unittest.skipUnless(shutil.which("jq"), "needs jq")
class StackCycle(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.home = self.dir / "home"
        self.state = self.home / ".local/state/stack"
        self.out = self.state / "cycle"
        (self.state / "observe").mkdir(parents=True)
        self.latest = self.state / "observe/latest.json"
        self.latest.write_text('{"version":1,"window":{"since":"2000-01-01T00:00:00Z","until":"2000-01-08T00:00:00Z"}}')
        self.checkout = self.dir / "checkout"
        (self.checkout / "home").mkdir(parents=True)
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        self.calls = self.dir / "calls"
        self.fake("stack", f'printf "%s %s\\n" "$4" "$(pwd -P)" >>{sh_quote(str(self.calls))}\n'
                           f'. {sh_quote(str(self.dir))}/"$4.sh"\n')
        self.fake("chezmoi", f"printf '%s\\n' {sh_quote(str(self.checkout / 'home'))}\n")
        self.stage("observe", body(dump(response("observe")), fresh=True))
        self.stage("improve", body(dump(response("improve", status="warn", findings=[{"kind": "x"}]))))
        jq = shutil.which("jq")
        self.path = os.pathsep.join([str(self.bin), os.path.dirname(jq), "/usr/bin", "/bin"])

    def fake(self, name, text):
        path = self.bin / name
        path.unlink(missing_ok=True)
        path.symlink_to(DISPATCH)
        Path(f"{path}.body").write_text(text)

    def stage(self, name, text):
        (self.dir / f"{name}.sh").write_text(text)

    def previous(self, last=True, error=False):
        self.out.mkdir(parents=True, exist_ok=True)
        if last:
            (self.out / "last.json").write_bytes(OLD_LAST)
        if error:
            (self.out / "last-error").write_bytes(OLD_ERROR)

    def env(self):
        return {"HOME": str(self.home), "PATH": self.path, "LC_ALL": "C"}

    def run_cycle(self):
        return subprocess.run(["/bin/sh", str(SCRIPT)], env=self.env(), cwd=self.dir, capture_output=True, text=True,
                              timeout=30)

    def called(self):
        return [line.split(" ", 1)[0] for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def assert_failed(self, result, message):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(message, result.stderr)
        when, text = (self.out / "last-error").read_text().splitlines()
        self.assertRegex(when, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(text, message)
        self.assert_no_temp()

    def assert_no_temp(self):
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.startswith(".")], [])

    def test_both_valid_replaces_last_json_and_removes_last_error(self):
        self.previous(error=True)
        result = self.run_cycle()
        self.assertEqual(result.returncode, 0, result.stderr)
        last = json.loads((self.out / "last.json").read_text())
        self.assertEqual(last["stage"], "cycle")
        self.assertEqual(last["status"], "warn")
        self.assertEqual([r["name"] for r in last["results"]], ["observe", "improve"])
        self.assertEqual(last["skipped"], [])
        self.assertFalse((self.out / "last-error").exists())
        self.assertEqual(self.calls.read_text().splitlines(),
                         [f"observe {self.checkout.resolve()}", f"improve {self.checkout.resolve()}"])
        self.assert_no_temp()

    def test_first_valid_run_creates_the_state_directory(self):
        result = self.run_cycle()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.out / "last.json").read_text())["status"], "warn")

    def test_both_pass_gives_pass(self):
        self.stage("improve", body(dump(response("improve"))))
        self.assertEqual(self.run_cycle().returncode, 0)
        self.assertEqual(json.loads((self.out / "last.json").read_text())["status"], "pass")

    def test_invalid_improve_keeps_previous_last_json(self):
        for case, make in INVALID.items():
            with self.subTest(case):
                self.previous()
                self.calls.unlink(missing_ok=True)
                output, code = make("improve")
                self.stage("improve", body(output, code))
                result = self.run_cycle()
                self.assert_failed(result, f"improve: exit {code} without a valid result")
                self.assertEqual((self.out / "last.json").read_bytes(), OLD_LAST)
                self.assertEqual(self.called(), ["observe", "improve"])

    def test_invalid_observe_does_not_run_improve(self):
        for case, make in INVALID.items():
            with self.subTest(case):
                self.previous(error=True)
                self.calls.unlink(missing_ok=True)
                output, code = make("observe")
                self.stage("observe", body(output, code, fresh=True))
                result = self.run_cycle()
                self.assert_failed(result, f"observe: exit {code} without a valid result")
                self.assertEqual((self.out / "last.json").read_bytes(), OLD_LAST)
                self.assertEqual(self.called(), ["observe"])

    def test_stale_latest_json_does_not_run_improve(self):
        self.previous()
        self.stage("observe", body(dump(response("observe"))))  # latest.json keeps its window from 2000
        result = self.run_cycle()
        self.assert_failed(result, "observe did not write a fresh latest.json")
        self.assertEqual((self.out / "last.json").read_bytes(), OLD_LAST)
        self.assertEqual(self.called(), ["observe"])

    def test_latest_not_written_finding_does_not_run_improve(self):
        # latest.json ends in the job's own second, as one written by an earlier run in that second would
        self.previous()
        finding = {"kind": "latest-not-written", "message": "rename failed"}
        self.stage("observe", body(dump(response("observe", status="warn", findings=[finding])), fresh=True))
        result = self.run_cycle()
        self.assert_failed(result, "observe could not write latest.json")
        self.assertEqual((self.out / "last.json").read_bytes(), OLD_LAST)
        self.assertEqual(self.called(), ["observe"])

    def test_chezmoi_failure_does_not_run_stack(self):
        for case, text in {"fails": "exit 1\n", "prints nothing": "exit 0\n"}.items():
            with self.subTest(case):
                self.previous()
                self.fake("chezmoi", text)
                result = self.run_cycle()
                message = "chezmoi source-path failed" if case == "fails" else "chezmoi source-path printed nothing"
                self.assert_failed(result, message)
                self.assertEqual((self.out / "last.json").read_bytes(), OLD_LAST)
                self.assertEqual(self.called(), [])

    def assert_unwritable(self, directory):
        directory.chmod(0o500)
        try:
            result = self.run_cycle()
        finally:
            directory.chmod(0o700)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.called(), [])
        self.assertFalse((self.out / "last-error").exists())

    @unittest.skipIf(os.geteuid() == 0, "root writes to read-only directories")
    def test_unwritable_state_directory_does_not_run_stack(self):
        self.out.mkdir()
        self.assert_unwritable(self.out)

    @unittest.skipIf(os.geteuid() == 0, "root writes to read-only directories")
    def test_uncreatable_state_directory_does_not_run_stack(self):
        self.assert_unwritable(self.state)
        self.assertFalse(self.out.exists())

    def blocked(self, release_path, ready):
        """Start the cycle, wait until the fake signals ready, and return the running process."""
        os.mkfifo(release_path)
        proc = subprocess.Popen(["/bin/sh", str(SCRIPT)], env=self.env(), cwd=self.dir, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        deadline = time.monotonic() + 20
        while not ready.exists():
            if proc.poll() is not None:
                self.fail(f"the cycle ended before the fake blocked: {proc.communicate()[1]}")
            self.assertLess(time.monotonic(), deadline, "the fake never blocked")
            time.sleep(0.02)
        return proc

    def assert_previous_error(self, existed):
        if existed:
            self.assertEqual((self.out / "last-error").read_bytes(), OLD_ERROR)
        else:
            self.assertFalse((self.out / "last-error").exists())

    def release(self, proc, release_path):
        with open(release_path, "w"):
            pass
        out, err = proc.communicate(timeout=20)
        return proc.returncode, err

    def test_half_written_improve_output_never_reaches_last_json(self):
        for error in (False, True):
            with self.subTest(previous_error=error):
                self.previous(error=error)
                fifo, ready = self.dir / "release", self.dir / "ready"
                fifo.unlink(missing_ok=True)
                ready.unlink(missing_ok=True)
                text = dump(response("improve"))
                half = len(text) // 2
                self.stage("improve", f"printf '%s' {sh_quote(text[:half])}\n: >{sh_quote(str(ready))}\n"
                                      f"cat {sh_quote(str(fifo))} >/dev/null\n"
                                      f"printf '%s' {sh_quote(text[half:])}\n")
                proc = self.blocked(fifo, ready)
                self.assertEqual((self.out / "last.json").read_bytes(), OLD_LAST)
                self.assert_previous_error(error)
                code, err = self.release(proc, fifo)
                self.assertEqual(code, 0, err)
                self.assertEqual(len(json.loads((self.out / "last.json").read_text())["results"]), 2)
                self.assertFalse((self.out / "last-error").exists())

    def test_half_written_last_error_is_never_visible(self):
        for error in (False, True):
            with self.subTest(previous_error=error):
                self.previous(error=error)
                fifo, ready, count = self.dir / "release", self.dir / "ready", self.dir / "date-count"
                for p in (fifo, ready, count):
                    p.unlink(missing_ok=True)
                self.stage("improve", body("", 0))
                # The second date call is the timestamp line of last-error (the first is the job start): print it,
                # then block before the message line is written
                self.fake("date", f'n=$(($(cat {sh_quote(str(count))} 2>/dev/null || echo 0) + 1))\n'
                                  f'echo "$n" >{sh_quote(str(count))}\n'
                                  f'{sh_quote(DATE)} "$@" || exit\n'
                                  f'if [ "$n" -eq 2 ]; then : >{sh_quote(str(ready))}; '
                                  f'cat {sh_quote(str(fifo))} >/dev/null; fi\n')
                proc = self.blocked(fifo, ready)
                self.assert_previous_error(error)
                self.assertEqual((self.out / "last.json").read_bytes(), OLD_LAST)
                code, err = self.release(proc, fifo)
                self.assertEqual(code, 2, err)
                self.assertEqual((self.out / "last-error").read_text().splitlines()[1],
                                 "improve: exit 0 without a valid result")


if __name__ == "__main__":
    unittest.main()
