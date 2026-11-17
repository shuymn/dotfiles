#!/usr/bin/python3 -I
"""Keep an orchestration's state on disk and in front of its sessions.

~/.claude/worker-signals.json:
  {"workers": {"/abs/worktree": "/abs/signals/4", ...},
   "orchestrators": {"/abs/orchestrator/dir": "/abs/signals",
                     "/abs/cwd": {"state": "/abs/state/dir", "signals": "/abs/signals"}, ...}}
(The string form means the orchestrator dir itself holds the state.)

Worker session (cwd inside a listed worktree):
  Stop                         -> save the last assistant text to <stem>.report.md, touch <stem>.done
  PreToolUse(AskUserQuestion)  -> touch <stem>.question
Orchestrator session (cwd inside a listed dir):
  Stop, while workers are listed (blocks once per stop; stop_hook_active lets the next stop pass):
    - no live waiter (<signals>/.waiter/pid) -> ask to start it
Context injection and state freshness belong to orchestration-context.py (list <signals>/seen in the
kit's `watch` file). Other sessions are untouched. Remove a worker entry when its worker is done;
delete the file when no orchestration uses it.
"""
import json
import os
import sys

MAP = os.path.expanduser("~/.claude/worker-signals.json")


def inside(cwd, table):
    for root, value in table.items():
        real = os.path.realpath(os.path.expanduser(root))
        if cwd == real or cwd.startswith(real + os.sep):
            return real, value
    return None, None


def touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8"):
        os.utime(path)


def last_assistant_text(transcript):
    try:
        with open(transcript, encoding="utf-8") as f:
            lines = f.readlines()[-400:]
    except (OSError, TypeError):
        return None
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "assistant":
            continue
        texts = [b.get("text", "") for b in entry.get("message", {}).get("content", [])
                 if isinstance(b, dict) and b.get("type") == "text"]
        if any(t.strip() for t in texts):
            return "\n".join(texts)
    return None


def waiter_alive(signals):
    try:
        with open(os.path.join(signals, ".waiter", "pid"), encoding="utf-8") as f:
            os.kill(int(f.read().strip()), 0)
        return True
    except (FileNotFoundError, ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True


def block(reason):
    json.dump({"decision": "block", "reason": reason}, sys.stdout)
    return 0


def main():
    try:
        with open(MAP, encoding="utf-8") as f:
            table = json.load(f)
    except (FileNotFoundError, ValueError):
        return 0
    event = json.load(sys.stdin)
    cwd = os.path.realpath(event.get("cwd") or os.getcwd())
    name = event.get("hook_event_name", "")
    workers = table.get("workers", {})

    _, stem = inside(cwd, workers)
    if stem is not None:
        stem = os.path.expanduser(stem)
        if name == "Stop":
            text = last_assistant_text(event.get("transcript_path"))
            if text:
                with open(stem + ".report.md", "w", encoding="utf-8") as f:
                    f.write(text + "\n")
            touch(stem + ".done")
        elif name == "PreToolUse" and event.get("tool_name") == "AskUserQuestion":
            touch(stem + ".question")
        return 0

    orch, signals = inside(cwd, table.get("orchestrators", {}))
    if orch is None:
        return 0
    if isinstance(signals, dict):  # {"state": the kit (read by orchestration-context.py), "signals": dir}
        signals = signals["signals"]
    if name != "Stop" or not workers or event.get("stop_hook_active"):
        return 0
    signals = os.path.expanduser(signals)
    if not waiter_alive(signals):
        return block(f"Workers are listed in {MAP} but no signal waiter runs for {signals}. "
                     "Start the waiter as a background command, or remove finished workers from the map.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
