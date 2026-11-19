#!/usr/bin/python3 -I
"""Keep an orchestration's essence in front of its sessions, whatever the context did to the conversation.

A kit is the directory holding an orchestration's state: NORTH.md and/or state.md (essence first), optional
bin/board (prints live state), attention/items.json (the kit's attention register) and an optional `watch`
file (paths whose change means the state file is stale). The hook finds the kit from cwd or an ancestor of it:
  - ~/.claude/projects/<dir, non-alphanumerics as ->/*-orchestration/
  - an "orchestrators" entry of ~/.claude/worker-signals.json for that dir: {"/dir": "/signals"} (the dir holds
    the state) or {"/dir": {"state": "/kit", "signals": "/signals"}}
A worker listed under "workers" in that file gets only the worker items. Other sessions get nothing.

SessionStart (startup, resume, clear, compact): orchestrator -> state files, orchestrator items (global register +
  kit register), the budget line, the macro questions, then the board output (the only part that is cut to fit).
  This text, not the compaction summary, is the source of truth after a compaction.
SessionStart (compact) of a worker, any cwd: when the first non-meta user message of the transcript holds WORKER_LINE
  (the fixed line of a worker brief, anywhere in the message), the body of ../agents/opus-worker.md (next to this
  hook's directory, frontmatter stripped) and that message verbatim go first, ahead of any text above, all cut to fit.
Stop: blocks once when a path in `watch` is newer than the state file (state.md, else units.json). A touch
  acknowledges "nothing changed".
Never fails a session: any error means no output and exit 0.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True  # importing the budget hook must not leave __pycache__ in hooks/
CLAUDE = Path.home() / ".claude"
SIGNALS_MAP = CLAUDE / "worker-signals.json"
BUDGET_HOOK = CLAUDE / "hooks" / "attention-budget.py"
GLOBAL_REGISTER = CLAUDE / "attention" / "items.json"
WORKER_BODY = Path(__file__).resolve().parent.parent / "agents" / "opus-worker.md"
WORKER_LINE = "Follow the body of ~/.claude/agents/opus-worker.md"
STATE_FILES = ("NORTH.md", "state.md")  # injected, in this order
FRESH_FILES = ("state.md", "units.json")  # the volatile state a Stop check compares against `watch`
MAX_CHARS = 9_500  # the harness may cap hook context near 10,000 characters
BLOCK_CHARS = 4_500
STATE_LIMIT = 3_000  # a state file past this is accumulating history
SLACK = 30  # seconds
BOARD_SECONDS = 40  # one deadline for all boards, under the hook timeout
IGNORE = "If you were not handed this orchestration (a planner, or a product agent in the same checkout), ignore this."
QUESTIONS = (
    "Before the next completion: is the critical path to the purpose moving, and is its blocker being worked? Is anything "
    "running that does not serve it (cancel, defer, track)? Very long session at a step boundary with no delegate "
    "running or awaiting follow-up: hand over to a fresh orchestrator thread without asking (hiden "
    "references/attention.md)."
)


def real(path):
    return os.path.realpath(os.path.expanduser(str(path)))


def inside(cwd, root):
    root = real(root)
    return cwd == root or cwd.startswith(root + os.sep)


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def load_map():
    try:
        data = json.loads(read_text(SIGNALS_MAP))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def orchestrators():
    """[(dir, kit, signals or None)] from the map; the string form means the dir itself holds the state."""
    out = []
    table = load_map().get("orchestrators", {})
    for key, val in (table.items() if isinstance(table, dict) else []):
        if isinstance(val, dict) and isinstance(val.get("state", key), str):
            out.append((real(key), real(val.get("state", key)), real(val["signals"]) if val.get("signals") else None))
        elif isinstance(val, str):
            out.append((real(key), real(key), real(val)))
    return out


def ancestors(path):
    home = str(Path.home())
    for a in [Path(path), *Path(path).parents]:
        if str(a) in (home, "/"):
            break
        yield str(a)


def find_kits(cwd):
    raw = cwd.rstrip("/") or "/"
    levels = []
    for base in (raw, real(raw)):
        levels += [a for a in ancestors(base) if a not in levels]
    table = orchestrators()
    for a in levels:
        kits = sorted(p for p in (CLAUDE / "projects" / re.sub(r"[^A-Za-z0-9]", "-", a)).glob("*-orchestration") if p.is_dir())
        kits += [Path(kit) for key, kit, _ in table if key == real(a) and Path(kit) not in kits]
        if kits:
            return kits
    return []


def worker_kit(cwd):
    """(is a listed worker, kit of the orchestrator whose signals directory holds its signal files)."""
    workers = load_map().get("workers", {})
    for worktree, stem in (workers.items() if isinstance(workers, dict) else []):
        if inside(real(cwd), worktree):
            for _, kit, signals in orchestrators():
                if signals and inside(real(stem), signals):
                    return True, Path(kit)
            return True, None
    return False, None


def read_items(path):
    try:
        items = json.loads(read_text(path)).get("items", [])
    except (OSError, ValueError, AttributeError):
        return []
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def rules(items, roles):
    return "\n".join(f"- {i['rule']}" for i in items if i.get("role") in roles and isinstance(i.get("rule"), str))


def budget_line(items):
    """Usage of the cap for this session (global + its kit), counted by the budget hook's own code."""
    try:
        spec = importlib.util.spec_from_file_location("attention_budget", BUDGET_HOOK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        caps = mod.load_budget()["caps"]
        counts = mod.role_counts(items, caps)
    except Exception:  # the budget is advice here; never block a session start on it
        return ""
    over = [r for r, c in caps.items() if counts.get(r, 0) > c]
    return (f"Attention budget (global + this kit): orchestrator {counts.get('orchestrator', 0)}/{caps.get('orchestrator', '?')}"
            + (f"; OVER: {', '.join(over)}" if over else "")
            + ". At a cap a new rule replaces one or becomes a mechanism, even if the owner asks.")


def cut(text, limit):
    return text if len(text) <= limit else text[:limit].rstrip() + "\n[...cut]"


def state_blocks(kit):
    parts, bodies = [], []
    for name in STATE_FILES:
        f = kit / name
        if f.is_file():
            body = read_text(f).strip()
            size = len(body.encode("utf-8", "replace"))
            note = f"[{name} is {size} bytes, over {STATE_LIMIT}: rewrite it shorter now; it holds the current state, not history.]\n" if size > STATE_LIMIT else ""
            bodies.append(body)
            parts.append(f'<orchestration-state path="{f}">\n{note}{cut(body, BLOCK_CHARS)}\n</orchestration-state>')
    return parts, bodies


def board_text(kit, bodies, deadline):
    """The board's output without the state files it repeats, or a marker when it failed."""
    board = kit / "bin" / "board"
    if not os.access(board, os.X_OK):
        return None
    try:
        p = subprocess.run([str(board)], capture_output=True, text=True, errors="replace",
                           timeout=max(1.0, deadline - time.monotonic()), cwd=str(kit))
    except subprocess.TimeoutExpired:
        return board, "[board timed out]"
    except OSError as e:
        return board, f"[board failed: {e}]"
    out = p.stdout.strip()
    for body in bodies:
        if body and out.startswith(body):
            out = out[len(body):].lstrip()
    if p.returncode != 0 or not out:
        err = (p.stderr.strip().splitlines() or ["no output"])[-1]
        out = (out + "\n" if out else "") + f"[board exit {p.returncode}: {err}]"
    return board, out


def emit(text):
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, sys.stdout)


def kit_context(data):
    """The orchestrator's or a listed worker's context for this cwd, or None."""
    cwd = data.get("cwd") or os.getcwd()
    items = read_items(GLOBAL_REGISTER)
    is_worker, kit = worker_kit(cwd)
    if is_worker:
        if kit:
            items += read_items(kit / "attention" / "items.json")
        text = rules(items, ("worker", "all"))
        return "You are a worker in an orchestration. Always-on rules (the packet has the rest):\n" + text if text else None
    kits = find_kits(cwd)
    if not kits:
        return None
    parts, bodies = [], []
    for kit in kits:
        p, b = state_blocks(kit)
        parts += p
        bodies += b
        items += read_items(kit / "attention" / "items.json")
    parts.append(f"<orchestrator-attention-items>\n{rules(items, ('orchestrator', 'all'))}\n</orchestrator-attention-items>")
    parts += [budget_line(items), QUESTIONS]
    head = ("This session orchestrates this work: the text below is the source of truth over a compaction summary; after a "
            "compaction also re-read the hiden reference for your current stage. " + IGNORE + "\n\n"
            + "\n\n".join(p for p in parts if p))
    deadline = time.monotonic() + BOARD_SECONDS
    text = head
    for kit in kits:
        got = board_text(kit, bodies, deadline)
        if not got:
            continue
        open_tag, close_tag = f'\n\n<orchestration-board path="{got[0]}">\n', "\n</orchestration-board>"
        room = MAX_CHARS - len(text) - len(open_tag) - len(close_tag) - len("\n[...cut]")
        if room < 200:
            text += "\n\n[board omitted: context limit]"
            break
        text += open_tag + cut(got[1], room) + close_tag
    return text


def first_prompt(transcript):
    """The text of the first user message that is not meta, a compaction summary or a tool result."""
    with open(transcript, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("type") != "user" or d.get("isMeta") or d.get("isCompactSummary"):
                continue
            content = d["message"]["content"]
            if isinstance(content, str):
                return content
            texts = [b["text"] for b in content if b.get("type") == "text"]
            if texts:
                return "\n\n".join(texts)
            if not any(b.get("type") == "tool_result" for b in content):
                return ""
    return None


def worker_brief(data):
    """After a compaction, the worker body and the original brief verbatim, for a session briefed by WORKER_LINE."""
    prompt = first_prompt(data["transcript_path"]) if data.get("transcript_path") else None
    if not prompt or WORKER_LINE not in prompt:
        return None
    body = read_text(WORKER_BODY)
    body = re.sub(r"\A---\n.*?\n---\n", "", body, count=1, flags=re.S).strip()
    return ("A compaction summarized this conversation; the verbatim worker rules and your original brief follow.\n\n"
            f"<worker-rules path=\"{WORKER_BODY}\">\n{body}\n</worker-rules>\n\n"
            f"<original-brief>\n{prompt}\n</original-brief>")


def session_start(data):
    if data.get("source") not in ("compact", "resume", "startup", "clear"):
        return
    text = kit_context(data)
    try:
        brief = worker_brief(data) if data.get("source") == "compact" else None
    except Exception:  # a broken transcript must not cost the orchestrator its context
        brief = None
    if brief:
        text = cut(brief + ("\n\n" + text if text else ""), MAX_CHARS - len("\n[...cut]"))
    if text:
        emit(text)


def newest(path):
    try:
        if os.path.isdir(path):
            return max((os.path.getmtime(os.path.join(path, n)) for n in os.listdir(path)), default=0)
        return os.path.getmtime(path)
    except OSError:
        return 0


def stop(data):
    if data.get("stop_hook_active"):
        return
    for kit in find_kits(data.get("cwd") or os.getcwd()):
        watch = kit / "watch"
        state = next((kit / n for n in FRESH_FILES if (kit / n).is_file()), None)
        if state is None or not watch.is_file():
            continue
        lines = [l.strip() for l in read_text(watch).splitlines() if l.strip() and not l.startswith("#")]
        paths = [os.path.expanduser(l) if os.path.isabs(os.path.expanduser(l)) else str(kit / l) for l in lines]
        stale = [p for p in paths if newest(p) > state.stat().st_mtime + SLACK]
        if stale:
            json.dump({"decision": "block", "reason": (
                f"{', '.join(stale)} changed after {state}. Rewrite the state (current state only) so it matches, or touch it "
                f"if nothing changed; then answer: {QUESTIONS} {IGNORE}")}, sys.stdout)
            return


def main():
    try:
        data = json.load(sys.stdin)
        event = data.get("hook_event_name") if isinstance(data, dict) else None
        if event == "Stop":
            stop(data)
        elif event in (None, "SessionStart"):
            session_start(data)
    except Exception:  # a hook must never fail a session
        return


if __name__ == "__main__":
    main()
