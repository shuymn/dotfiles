from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "home/dot_claude/hooks/executable_orchestration-context.py"
BODY = REPO / "home/dot_claude/agents/opus-worker.md"
SETTINGS = REPO / "home/dot_claude/modify_private_settings.json"
# The hook before the worker brief branch; its SessionStart and Stop output is the reference.
BEFORE_UNITS = "83034fe07f89843d6c99d10e4e80141dc85ee9e2"
LINE = "Follow the body of ~/.claude/agents/opus-worker.md."
RULE = ("A test counts as a regression test only after it has been seen failing with the fix removed and passing with "
        "it restored.")


class HookCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="orchestration-context-test-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        self.home = self.tmp / "home"
        self.repo = self.tmp / "work" / "repo"
        for d in (self.home, self.repo / ".git"):
            d.mkdir(parents=True)
        self.env = {**os.environ, "HOME": str(self.home)}

    def run_hook(self, data, hook=HOOK):
        p = subprocess.run([sys.executable, "-I", str(hook)], input=json.dumps(data), capture_output=True, text=True,
                           env=self.env, timeout=30)
        self.assertEqual((p.returncode, p.stderr), (0, ""))
        return p.stdout

    def transcript(self, *records, name="t.jsonl", raw=None):
        path = self.tmp / name
        path.write_text(raw if raw is not None else "".join(json.dumps(r) + "\n" for r in records))
        return path

    @staticmethod
    def user(content, **extra):
        return {"type": "user", "message": {"role": "user", "content": content}, **extra}

    def start(self, path, source="compact"):
        return {"hook_event_name": "SessionStart", "source": source, "cwd": str(self.repo), "session_id": "s",
                "transcript_path": str(path)}


class WorkerBriefTest(HookCase):
    BRIEF = f"Act as the implementation sub-agent for this task.\n\n{LINE}\n\n## Task\nFix the pager."

    def context(self, out):
        got = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(got["hookEventName"], "SessionStart")
        return got["additionalContext"]

    def test_fixed_line_after_other_text_injects_body_and_brief(self):
        path = self.transcript({"type": "queue-operation"}, self.user("<local-command-caveat>x</local-command-caveat>",
                                                                      isMeta=True),
                               self.user(self.BRIEF), {"type": "system", "subtype": "compact_boundary"},
                               self.user("Summary of the session.", isCompactSummary=True))
        text = self.context(self.run_hook(self.start(path)))
        self.assertTrue(text.startswith("A compaction summarized this conversation"), text)
        self.assertEqual(text.count("\n\n<worker-rules"), 1)
        self.assertIn(RULE, text)
        self.assertIn(BODY.read_text().split("---\n", 2)[2].strip(), text)
        self.assertNotIn("name: opus-worker", text)
        self.assertTrue(text.endswith(f"<original-brief>\n{self.BRIEF}\n</original-brief>"), text)
        self.assertNotIn("Summary of the session.", text)

    def test_text_blocks_and_tool_results(self):
        blocks = [{"type": "text", "text": "Act as the sub-agent."}, {"type": "text", "text": LINE}]
        path = self.transcript(self.user([{"type": "tool_result", "tool_use_id": "x", "content": LINE}]),
                               self.user(blocks))
        self.assertIn(f"<original-brief>\nAct as the sub-agent.\n\n{LINE}\n</original-brief>",
                      self.context(self.run_hook(self.start(path))))

    def test_long_brief_is_cut_to_the_limit(self):
        path = self.transcript(self.user(f"{LINE}\n" + "x" * 20_000))
        text = self.context(self.run_hook(self.start(path)))
        self.assertLessEqual(len(text), 9_500)
        self.assertTrue(text.endswith("\n[...cut]"))
        self.assertIn(RULE, text)

    def test_no_fixed_line_no_output(self):
        for records in ([self.user("Fix the pager. Read the opus-worker body."), self.user(f"later: {LINE}")],
                        [self.user(f"meta: {LINE}", isMeta=True), self.user("Fix the pager.")],
                        [self.user(f"summary: {LINE}", isCompactSummary=True), self.user("Fix the pager.")],
                        [self.user(f'In worker briefs, include "{LINE}"'), self.user(self.BRIEF)],
                        [self.user(self.BRIEF, isSidechain=True), self.user("Orchestrate the work.")]):
            with self.subTest(records=records):
                self.assertEqual(self.run_hook(self.start(self.transcript(*records))), "")

    def test_sidechain_before_the_brief_is_skipped(self):
        path = self.transcript(self.user("Orchestrate the work.", isSidechain=True), self.user(self.BRIEF))
        self.assertIn(f"<original-brief>\n{self.BRIEF}\n</original-brief>", self.context(self.run_hook(self.start(path))))

    def test_unreadable_kit_keeps_the_worker_rules(self):
        kit = self.home / ".claude/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(self.repo)) / "x-orchestration"
        kit.mkdir(parents=True)
        (kit / "state.md").write_text("# state\n")
        (kit / "state.md").chmod(0)
        self.addCleanup((kit / "state.md").chmod, 0o600)
        text = self.context(self.run_hook(self.start(self.transcript(self.user(self.BRIEF)))))
        self.assertIn(RULE, text)

    def test_only_compaction_injects(self):
        path = self.transcript(self.user(self.BRIEF))
        for source in ("startup", "resume", "clear", "other"):
            with self.subTest(source=source):
                self.assertEqual(self.run_hook(self.start(path, source)), "")
        self.assertEqual(self.run_hook({**self.start(path), "hook_event_name": "Stop"}), "")

    def test_bad_transcript_no_output(self):
        cases = {"missing": None, "not json": "{not json\n" + json.dumps(self.user(self.BRIEF)) + "\n",
                 "not an object": "[1]\n", "no message": json.dumps({"type": "user"}) + "\n",
                 "content not text": json.dumps(self.user(5)) + "\n", "empty": ""}
        for name, raw in cases.items():
            with self.subTest(name):
                path = self.tmp / "absent.jsonl" if raw is None else self.transcript(raw=raw, name=f"{len(name)}.jsonl")
                self.assertEqual(self.run_hook(self.start(path)), "")
        self.assertEqual(self.run_hook({k: v for k, v in self.start(path).items() if k != "transcript_path"}), "")
        self.assertEqual(self.run_hook({**self.start(path), "transcript_path": 7}), "")

    def test_listed_worker_gets_brief_then_its_rules(self):
        claude = self.home / ".claude"
        (claude / "attention").mkdir(parents=True)
        (claude / "attention" / "items.json").write_text(json.dumps({"items": [
            {"id": "w", "role": "worker", "rule": "worker rule."}]}))
        (claude / "worker-signals.json").write_text(json.dumps({"workers": {str(self.repo): str(self.tmp / "sig")}}))
        path = self.transcript(self.user(self.BRIEF))
        text = self.context(self.run_hook(self.start(path)))
        self.assertTrue(text.startswith("A compaction summarized"), text)
        self.assertTrue(text.endswith("You are a worker in an orchestration. Always-on rules (the packet has the "
                                      "rest):\n- worker rule."), text)
        self.assertEqual(self.context(self.run_hook(self.start(path, "resume"))),
                         "You are a worker in an orchestration. Always-on rules (the packet has the rest):\n- worker rule.")


class UnchangedEventsTest(HookCase):
    """SessionStart and Stop output equal the reference hook's output for the same inputs when no worker brief applies."""

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
        self.plain = self.tmp / "plain.jsonl"
        self.plain.write_text(json.dumps(self.user("Run the orchestration; workers follow opus-worker.md.")) + "\n")

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
                    outputs.append(self.assert_same({**data, "transcript_path": str(self.plain)}))
                    outputs.append(self.assert_same({**data, "transcript_path": str(self.tmp / "absent.jsonl")}))
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


def managed_hooks():
    return json.loads(re.search(r"\$managed := `\n(.*?)\n` \| mustFromJson", SETTINGS.read_text(), re.S).group(1))["hooks"]


class SettingsTest(unittest.TestCase):
    BUDGET = {"matcher": "Edit|Write|MultiEdit", "hooks": [{"type": "command", "command": "~/.claude/hooks/attention-budget.py pre"}]}
    START = {"hooks": [{"type": "command", "command": "~/.claude/hooks/orchestration-context.py", "timeout": 60}]}

    def assert_hooks(self, hooks):
        self.assertIn(self.BUDGET, hooks["PreToolUse"])
        self.assertEqual(hooks["SessionStart"], [self.START])

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



if __name__ == "__main__":
    unittest.main()
