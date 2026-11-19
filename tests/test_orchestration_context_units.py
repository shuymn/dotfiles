from pathlib import Path
from unittest import mock
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "home/dot_claude/hooks/executable_orchestration-context.py"
UNITS = REPO / "home/dot_claude/attention/units.json"
SETTINGS = REPO / "home/dot_claude/modify_private_settings.json"
# The hook before the PostToolUse branch; its SessionStart and Stop output is the reference.
BEFORE_UNITS = "83034fe07f89843d6c99d10e4e80141dc85ee9e2"
TEXT = ("A test counts as a regression test only after it has been seen failing with the fix removed and passing with "
        "it restored.")
EXPECTED = json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": TEXT}})


class HookCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="units-test-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        self.home = self.tmp / "home"
        self.tmpdir = self.tmp / "tmp"
        self.repo = self.tmp / "work" / "repo"
        for d in (self.home, self.tmpdir, self.repo / ".git"):
            d.mkdir(parents=True)
        self.env = {**os.environ, "HOME": str(self.home), "TMPDIR": str(self.tmpdir)}
        self.markers = self.tmpdir / "claude-units"

    def run_hook(self, data, hook=HOOK):
        p = subprocess.run([sys.executable, "-I", str(hook)], input=json.dumps(data), capture_output=True, text=True,
                           env=self.env, timeout=30)
        self.assertEqual((p.returncode, p.stderr), (0, ""))
        return p.stdout

    def event(self, path, tool="Write", agent_id="agent-1", session_id="session-1", agent_type="opus-worker",
              cwd=None, name="PostToolUse"):
        path = Path(path) if os.path.isabs(path) else self.repo / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n")
        data = {"hook_event_name": name, "session_id": session_id, "cwd": str(cwd or self.repo), "tool_name": tool,
                "tool_input": {"file_path": str(path)}, "tool_response": {"filePath": str(path)}}
        if agent_id is not None:
            data["agent_id"] = agent_id
        if agent_type is not None:
            data["agent_type"] = agent_type
        return data

    def assert_emits(self, data, hook=HOOK):
        self.assertEqual(self.run_hook(data, hook), EXPECTED)

    def assert_silent(self, data, hook=HOOK):
        self.assertEqual(self.run_hook(data, hook), "")

    def marker_count(self):
        return len(list(self.markers.iterdir())) if self.markers.is_dir() else 0


class DeliveryTest(HookCase):
    def test_first_test_write_emits_unit(self):
        files = ["pkg/a_test.go", "web/a.test.ts", "web/a.test.tsx", "web/a.test.js", "web/a.spec.ts", "web/a.spec.js",
                 "py/test_a.py", "py/a_test.py", "tests/a.rs", "crates/x/tests/a.rs"]
        for i, f in enumerate(files):
            for tool in ("Edit", "Write", "MultiEdit"):
                with self.subTest(file=f, tool=tool):
                    self.assert_emits(self.event(f, tool=tool, agent_id=f"agent-{i}-{tool}"))

    def test_unit_file_is_found_next_to_the_hook_directory(self):
        self.assertEqual(json.loads(UNITS.read_text())["units"][0]["text"], TEXT)

    def test_second_write_silent(self):
        self.assert_emits(self.event("pkg/a_test.go"))
        self.assert_silent(self.event("pkg/b_test.go"))
        self.assert_silent(self.event("pkg/a_test.go", tool="Edit"))

    def test_sibling_agent_and_other_session_emit(self):
        self.assert_emits(self.event("pkg/a_test.go"))
        self.assert_emits(self.event("pkg/a_test.go", agent_id="agent-2"))
        self.assert_emits(self.event("pkg/a_test.go", session_id="session-2"))

    def test_parent_and_other_roles_silent(self):
        for kw in ({"agent_id": None}, {"agent_type": None}, {"agent_type": "general-purpose"}, {"agent_type": "Opus-Worker"},
                   {"agent_id": ""}, {"agent_id": 7}, {"agent_id": ["agent-1"]}, {"session_id": None}, {"session_id": ""}):
            with self.subTest(**{k: repr(v) for k, v in kw.items()}):
                self.assert_silent(self.event("pkg/a_test.go", **kw))
                self.assertEqual(self.marker_count(), 0)
        self.assert_emits(self.event("pkg/a_test.go"))

    def test_blank_or_control_ids_silent(self):
        for kw in ({"agent_id": "  "}, {"agent_id": "\t"}, {"session_id": " \n"}, {"agent_id": "agent\n1"},
                   {"agent_id": "a\x00"}, {"session_id": "s\x7f"}, {"agent_id": "a\x85"}, {"session_id": "s\x1b[0m"}):
            with self.subTest(**{k: repr(v) for k, v in kw.items()}):
                self.assert_silent(self.event("pkg/a_test.go", **kw))
                self.assertEqual(self.marker_count(), 0)
        self.assert_emits(self.event("pkg/a_test.go", agent_id="agent 1"))

    def test_non_test_paths(self):
        outside = self.tmp / "work" / "elsewhere"
        (self.repo / "link").symlink_to(outside, target_is_directory=True)
        for f in ["pkg/foo.go", "web/x.spec.tsx", "web/a.test.jsx", "tests/common/mod.rs", "src/a.rs", "tests/a.rs.bak",
                  "pkg/A_TEST.GO", str(outside / "a_test.go"), str(outside / "tests" / "a.rs"),
                  str(self.repo / "link" / "test_a.py")]:
            with self.subTest(file=f):
                self.assert_silent(self.event(f))
        self.assertEqual(self.marker_count(), 0)

    def test_later_test_write_still_emits(self):
        self.assert_silent(self.event("pkg/foo.go"))
        self.assert_silent(self.event(str(self.tmp / "work" / "elsewhere" / "a_test.go")))
        self.assert_emits(self.event("pkg/foo_test.go"))

    def test_tests_directory_above_the_root(self):
        repo = self.tmp / "tests" / "repo"
        (repo / ".git").mkdir(parents=True)
        self.assert_silent(self.event(str(repo / "a.rs"), cwd=repo))
        plain = self.tmp / "tests" / "plain"
        self.assert_silent(self.event(str(plain / "a.rs"), cwd=plain))
        self.assertEqual(self.marker_count(), 0)
        self.assert_emits(self.event(str(repo / "tests" / "a.rs"), cwd=repo))

    def test_git_file_worktree_root(self):
        wt = self.tmp / "tests" / "wt"
        (wt / "sub").mkdir(parents=True)
        (wt / ".git").write_text("gitdir: elsewhere\n")
        self.assert_silent(self.event(str(self.tmp / "tests" / "a.rs"), cwd=wt / "sub"))
        self.assert_silent(self.event(str(self.tmp / "tests" / "a_test.go"), cwd=wt / "sub"))
        self.assertEqual(self.marker_count(), 0)
        self.assert_emits(self.event(str(wt / "tests" / "a.rs"), cwd=wt / "sub"))

    def test_without_repo_cwd_is_the_root(self):
        plain = self.tmp / "plain"
        self.assert_silent(self.event(str(self.tmp / "other" / "test_a.py"), cwd=plain))
        self.assertEqual(self.marker_count(), 0)
        self.assert_emits(self.event(str(plain / "test_a.py"), cwd=plain))

    def test_bash_and_failure_events_silent(self):
        bash = self.event("pkg/a_test.go", tool="Bash")
        bash["tool_input"]["command"] = "touch pkg/a_test.go"
        self.assert_silent(bash)
        self.assert_silent(self.event("pkg/a_test.go", name="PostToolUseFailure"))
        self.assert_silent(self.event("pkg/a_test.go", name="PreToolUse"))
        self.assertEqual(self.marker_count(), 0)
        self.assert_emits(self.event("pkg/a_test.go"))

    def test_concurrent_claims(self):
        go = self.tmp / "go"
        waiter = ("import os, sys, time\nopen(sys.argv[2], 'w').close()\n"
                  "while not os.path.exists(sys.argv[1]): time.sleep(0.0005)\n"
                  "os.execv(sys.executable, [sys.executable, '-I', sys.argv[3]])\n")
        data = json.dumps(self.event("pkg/a_test.go"))
        procs = []
        for i in range(8):
            p = subprocess.Popen([sys.executable, "-c", waiter, str(go), str(self.tmp / f"ready-{i}"), str(HOOK)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 env=self.env)
            self.addCleanup(p.kill)
            p.stdin.write(data)
            p.stdin.close()
            procs.append(p)
        deadline = time.monotonic() + 30
        while not all((self.tmp / f"ready-{i}").exists() for i in range(8)):
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)
        go.touch()
        results = []
        for p in procs:
            p.wait(timeout=30)
            results.append((p.returncode, p.stdout.read(), p.stderr.read()))
            p.stdout.close()
            p.stderr.close()
        self.assertEqual([r[0] for r in results], [0] * 8)
        self.assertEqual([r[2] for r in results], [""] * 8)
        self.assertEqual(sorted(r[1] for r in results), [""] * 7 + [EXPECTED])

    def test_claim_is_atomic_across_threads(self):
        # Processes rarely meet inside the claim's few microseconds; threads switching every microsecond do.
        dont_write = sys.dont_write_bytecode
        self.addCleanup(setattr, sys, "dont_write_bytecode", dont_write)
        sys.dont_write_bytecode = True  # leave no __pycache__ next to the hook
        spec = importlib.util.spec_from_file_location("orchestration_context", HOOK)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        self.addCleanup(sys.setswitchinterval, sys.getswitchinterval())
        sys.setswitchinterval(1e-6)
        with mock.patch.object(tempfile, "tempdir", str(self.tmpdir)):
            for n in range(100):
                barrier, wins = threading.Barrier(8), []
                def contend():
                    barrier.wait()
                    wins.append(hook.claim("session-1", "agent-1", f"unit-{n}"))
                threads = [threading.Thread(target=contend) for _ in range(8)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                self.assertEqual(sorted(wins), [False] * 7 + [True], f"round {n}")


class FailureTest(HookCase):
    """A staged copy of the hook with its own units.json, so the checkout's file stays untouched."""

    def setUp(self):
        super().setUp()
        stage = self.tmp / "stage"
        (stage / "hooks").mkdir(parents=True)
        (stage / "attention").mkdir()
        self.hook = stage / "hooks" / "orchestration-context.py"
        shutil.copyfile(HOOK, self.hook)
        self.units = stage / "attention" / "units.json"

    def test_bad_units(self):
        good = json.loads(UNITS.read_text())
        bad_unit = {k: v for k, v in good["units"][0].items() if k != "text"}
        string_tools = {**good["units"][0], "tools": "Edit|Write|MultiEdit"}
        for name, body in [("missing", None), ("not json", "{"), ("no units", "{}"), ("units not a list", '{"units": 5}'),
                           ("list", "[]"), ("unit without text", json.dumps({"units": [bad_unit]})),
                           ("tools as a string", json.dumps({"units": [string_tools]}))]:
            with self.subTest(name):
                if body is None:
                    self.units.unlink(missing_ok=True)
                else:
                    self.units.write_text(body)
                self.assert_silent(self.event("pkg/a_test.go", tool="Edit"), self.hook)
                self.assertEqual(self.marker_count(), 0)
        shutil.copyfile(UNITS, self.units)
        self.assert_emits(self.event("pkg/a_test.go"), self.hook)

    def test_malformed_unit_is_skipped(self):
        good = json.loads(UNITS.read_text())["units"][0]
        for key, value in [("paths", ["*_test.go", 5]), ("paths", ["*_test.go", ""]), ("paths", ["*_test.go", None]),
                           ("tools", ["Write", ""]), ("tools", ["Write", ["Edit"]])]:
            with self.subTest(key=key, value=value):
                bad = {**good, key: value, "text": "MALFORMED"}
                self.units.write_text(json.dumps({"units": [bad, good]}))
                self.assert_emits(self.event("pkg/a_test.go", tool="Write", agent_id=f"{key}-{value!r}"), self.hook)

    def test_unwritable_state_dir(self):
        shutil.copyfile(UNITS, self.units)
        self.markers.write_text("not a directory\n")
        self.assert_silent(self.event("pkg/a_test.go"), self.hook)
        self.markers.unlink()
        self.markers.mkdir(mode=0o500)
        self.addCleanup(os.chmod, self.markers, 0o700)
        if not os.access(self.markers, os.W_OK):  # root can write anyway
            self.assert_silent(self.event("pkg/a_test.go"), self.hook)
        os.chmod(self.markers, 0o700)
        self.assert_emits(self.event("pkg/a_test.go"), self.hook)


class UnchangedEventsTest(HookCase):
    """SessionStart and Stop output equal the hook's output before the PostToolUse branch for the same inputs."""

    def setUp(self):
        super().setUp()
        p = subprocess.run(["git", "-C", str(REPO), "show", f"{BEFORE_UNITS}:{HOOK.relative_to(REPO)}"],
                           capture_output=True, text=True)
        if p.returncode != 0:
            self.skipTest("the reference commit is not in this clone")
        self.before = self.tmp / "before" / "hooks" / "orchestration-context.py"
        self.before.parent.mkdir(parents=True)
        # The reminder is wording revised on its own; the reference takes the current text so only the logic is compared.
        current = re.search(r"QUESTIONS = \(\n.*?\n\)", HOOK.read_text(), re.S).group(0)
        self.before.write_text(re.sub(r"QUESTIONS = \(\n.*?\n\)", lambda _: current, p.stdout, count=1, flags=re.S))
        claude = self.home / ".claude"
        (claude / "hooks").mkdir(parents=True)
        (claude / "hooks" / "attention-budget.py").write_text(
            "def load_budget():\n    return {'caps': {'orchestrator': 1, 'worker': 5}}\n"
            "def role_counts(items, caps):\n    out = {}\n"
            "    for i in items:\n        out[i.get('role')] = out.get(i.get('role'), 0) + 1\n    return out\n")
        self.write_items(claude / "attention" / "items.json", "global")
        self.kit = claude / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(self.repo)) / "demo-orchestration"
        self.write_items(self.kit / "attention" / "items.json", "kit")
        (self.kit / "NORTH.md").write_text("North: ship the demo.\n")
        (self.kit / "state.md").write_text("State: step 2 of 3.\n" + "x" * 3100 + "\n")
        board = self.kit / "bin" / "board"
        board.parent.mkdir()
        board.write_text("#!/bin/sh\necho 'board: two delegates running'\n")
        board.chmod(0o755)
        self.watched = self.tmp / "work" / "watched.txt"
        self.watched.write_text("w\n")
        (self.kit / "watch").write_text(f"# watched\n{self.watched}\n")
        self.worktree = self.tmp / "work" / "worker-wt"
        self.worktree.mkdir()
        signals = self.tmp / "signals"
        (claude / "worker-signals.json").write_text(json.dumps({
            "orchestrators": {str(self.repo): {"state": str(self.kit), "signals": str(signals)}},
            "workers": {str(self.worktree): str(signals / "w1")}}))

    @staticmethod
    def write_items(path, tag):
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"items": [{"id": f"{tag}-{r}", "role": r, "rule": f"{tag} rule for {r}."}
                                              for r in ("orchestrator", "worker", "reviewer", "all")]}))

    def assert_same(self, data):
        before, after = self.run_hook(data, self.before), self.run_hook(data, HOOK)
        self.assertEqual(after, before)
        return after

    def test_session_start_and_stop_unchanged(self):
        outputs = []
        for source in ("startup", "resume", "clear", "compact", "other"):
            for cwd in (self.repo, self.repo / "sub", self.worktree, self.tmp / "work"):
                with self.subTest(source=source, cwd=str(cwd)):
                    data = {"hook_event_name": "SessionStart", "source": source, "cwd": str(cwd), "session_id": "s"}
                    outputs.append(self.assert_same(data))
                    outputs.append(self.assert_same({k: v for k, v in data.items() if k != "hook_event_name"}))
        stop = {"hook_event_name": "Stop", "cwd": str(self.repo), "session_id": "s", "stop_hook_active": False}
        outputs.append(self.assert_same(stop))
        old = time.time() - 3600
        os.utime(self.kit / "state.md", (old, old))
        outputs.append(self.assert_same(stop))
        outputs.append(self.assert_same({**stop, "stop_hook_active": True}))
        joined = "".join(outputs)  # the fixture reaches every branch, so equality is not vacuous
        for part in ("<orchestration-state", "over 3000", "kit rule for orchestrator", "OVER: orchestrator",
                     "board: two delegates", "You are a worker", '"decision": "block"'):
            self.assertIn(part, joined)


# Ineligible events end in the shell: Python starts only for input that names opus-worker.
COMMAND = ('i=$(cat; echo .); case $i in *opus-worker*) printf %s "${i%.}" | ~/.claude/hooks/orchestration-context.py;; '
           'esac')


def managed_hooks():
    return json.loads(re.search(r"\$managed := `\n(.*?)\n` \| mustFromJson", SETTINGS.read_text(), re.S).group(1))["hooks"]


class SettingsTest(unittest.TestCase):
    ENTRY = {"matcher": "Edit|Write|MultiEdit", "hooks": [{"type": "command", "command": COMMAND, "timeout": 10}]}
    BUDGET = {"matcher": "Bash", "hooks": [{"type": "command", "command": "~/.claude/hooks/attention-budget.py post"}]}

    def assert_hooks(self, hooks):
        self.assertEqual(hooks["PostToolUse"], [self.BUDGET, self.ENTRY])
        self.assertEqual(hooks["PostToolUseFailure"], [self.BUDGET])

    def test_settings_registration(self):
        self.assert_hooks(managed_hooks())

    @unittest.skipUnless(shutil.which("chezmoi"), "chezmoi is not installed")
    def test_rendered_settings_keep_local_values(self):
        with tempfile.TemporaryDirectory() as home:
            env = {k: v for k, v in os.environ.items() if not k.startswith("XDG_")}
            env["HOME"] = home
            local_hook = {"matcher": "Read", "hooks": [{"type": "command", "command": "local-hook.sh"}]}
            existing = {"model": "sonnet", "localOnly": {"keep": True},
                        "permissions": {"additionalDirectories": ["/srv/shared"]},
                        "hooks": {"PostToolUse": [local_hook], "Notification": [local_hook]}}
            p = subprocess.run(["/bin/sh", str(SETTINGS)], input=json.dumps(existing), capture_output=True, text=True,
                               env=env, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assert_hooks(out["hooks"])
        # The template owns the whole hooks key: local hooks are replaced, not merged.
        self.assertEqual(out["hooks"], managed_hooks())
        self.assertEqual((out["model"], out["localOnly"]), ("sonnet", {"keep": True}))
        self.assertEqual(out["permissions"]["additionalDirectories"], ["/srv/shared"])
        self.assertIn("Bash(git:*)", out["permissions"]["allow"])


class CommandTest(HookCase):
    """The command string as configured, run by sh with the hook installed under HOME."""

    def setUp(self):
        super().setUp()
        hooks = self.home / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        (self.home / ".claude" / "attention").mkdir()
        shutil.copyfile(UNITS, self.home / ".claude" / "attention" / "units.json")
        self.hook = hooks / "orchestration-context.py"

    def install(self, source):
        self.hook.write_text(source)
        self.hook.chmod(0o755)

    def run_command(self, data):
        command = managed_hooks()["PostToolUse"][1]["hooks"][0]["command"]
        p = subprocess.run(["/bin/sh", "-c", command], input=data, capture_output=True, text=True, env=self.env,
                           timeout=30)
        return p.returncode, p.stdout, p.stderr

    def test_parent_event_ends_in_the_shell(self):
        self.install("#!/bin/sh\necho started >&2\nexit 3\n")
        for kw in ({"agent_type": None, "agent_id": None}, {"agent_type": "general-purpose"}):
            with self.subTest(**{k: repr(v) for k, v in kw.items()}):
                self.assertEqual(self.run_command(json.dumps(self.event("pkg/a_test.go", **kw))), (0, "", ""))

    def test_eligible_event_reaches_the_hook(self):
        self.install(HOOK.read_text().replace("#!/usr/bin/python3 -I", f"#!{sys.executable} -I", 1))
        self.assertEqual(self.run_command(json.dumps(self.event("pkg/a_test.go"))), (0, EXPECTED, ""))
        self.assertEqual(self.run_command(json.dumps(self.event("pkg/b_test.go"))), (0, "", ""))

    def test_input_reaches_the_hook_byte_identical(self):
        copy = self.tmp / "seen"
        self.install(f"#!/bin/sh\ncat > '{copy}'\n")
        for data in ('{"agent_type": "opus-worker"}', '{"agent_type": "opus-worker"}\n\n', ' opus-worker \\n $x `y` %s\n.'):
            with self.subTest(data=data):
                self.assertEqual(self.run_command(data), (0, "", ""))
                self.assertEqual(copy.read_bytes(), data.encode())


if __name__ == "__main__":
    unittest.main()
