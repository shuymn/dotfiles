from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SETTINGS = REPO / "home/dot_claude/modify_private_settings.json"


def managed_hooks():
    return json.loads(re.search(r"\$managed := `\n(.*?)\n` \| mustFromJson", SETTINGS.read_text(), re.S).group(1))["hooks"]


class SettingsTest(unittest.TestCase):
    # The core hook denies only raw merges, which are shell calls (Bash or PowerShell).
    GUARD = {"matcher": "Bash|PowerShell",
             "hooks": [{"type": "command", "command": "stack", "args": ["hook", "claude", "pre-tool-use"],
                        "timeout": 5, "onFailure": "continue"}]}
    GUARD_EXT = {"matcher": "Bash|PowerShell|Read|NotebookRead|Grep|Glob|mcp__pencil__execute",
                 "hooks": [{"type": "command", "command": "stack-guard", "args": ["hook", "claude", "pre-tool-use"],
                            "timeout": 5, "onFailure": "continue"}]}
    # Suffix regex so it also matches hosts that expose the tool under a prefixed name.
    ASK = {"matcher": "AskUserQuestion$",
           "hooks": [{"type": "command", "command": "~/.claude/hooks/ask-owner-checklist.sh", "timeout": 15,
                      "onFailure": "continue"}]}
    START = {"hooks": [{"type": "command", "command": "stack", "args": ["hook", "claude", "session-start"],
                        "timeout": 60, "onFailure": "continue"}]}

    def assert_hooks(self, hooks):
        self.assertIn(self.GUARD, hooks["PreToolUse"])
        self.assertIn(self.GUARD_EXT, hooks["PreToolUse"])
        self.assertIn(self.ASK, hooks["PreToolUse"])
        self.assertEqual(hooks["SessionStart"], [self.START])
        self.assertNotIn("Stop", hooks)
        commands = json.dumps(hooks)
        for retired in ("guard-agent-actions", "orchestration-context", "deny-rm", "attention-budget"):
            self.assertNotIn(retired, commands)

    def test_settings_registration(self):
        self.assert_hooks(managed_hooks())

    def render(self, existing, cardinal):
        """Run the modify script on existing, with or without a cardinal on PATH."""
        with tempfile.TemporaryDirectory() as home:
            env = {k: v for k, v in os.environ.items() if not k.startswith("XDG_")}
            env["HOME"] = home
            bin_dir = Path(home) / "bin"
            bin_dir.mkdir()
            (bin_dir / "chezmoi").symlink_to(shutil.which("chezmoi"))
            if cardinal:
                (bin_dir / "cardinal").write_text("#!/bin/sh\n")
                (bin_dir / "cardinal").chmod(0o755)
            env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
            p = subprocess.run(["/bin/sh", str(SETTINGS)], input=json.dumps(existing), capture_output=True, text=True,
                               env=env, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    @unittest.skipUnless(shutil.which("chezmoi"), "chezmoi is not installed")
    def test_rendered_settings_drop_cardinal_hooks_without_cardinal(self):
        hooks = self.render({}, cardinal=False)["hooks"]
        self.assert_hooks(hooks)
        self.assertNotIn("cardinal", json.dumps(hooks))
        for event in ("SubagentStop", "SessionEnd"):
            self.assertNotIn(event, hooks)
        expected = {event: [e for e in entries if not any(h["command"].startswith("cardinal ") for h in e["hooks"])]
                    for event, entries in managed_hooks().items()}
        self.assertEqual(hooks, {event: entries for event, entries in expected.items() if entries})

    @unittest.skipUnless(shutil.which("chezmoi"), "chezmoi is not installed")
    def test_rendered_settings_keep_local_values(self):
        local_hook = {"matcher": "Read", "hooks": [{"type": "command", "command": "local-hook.sh"}]}
        existing = {"model": "sonnet", "localOnly": {"keep": True},
                    "permissions": {"additionalDirectories": ["/srv/shared"]},
                    "hooks": {"PostToolUse": [local_hook], "Notification": [local_hook]}}
        out = self.render(existing, cardinal=True)
        self.assert_hooks(out["hooks"])
        # The template owns the whole hooks key: local hooks are replaced, not merged.
        self.assertEqual(out["hooks"], managed_hooks())
        self.assertEqual((out["model"], out["localOnly"]), ("sonnet", {"keep": True}))
        self.assertEqual(out["permissions"]["additionalDirectories"], ["/srv/shared"])
        self.assertIn("Bash(git:*)", out["permissions"]["allow"])


if __name__ == "__main__":
    unittest.main()
