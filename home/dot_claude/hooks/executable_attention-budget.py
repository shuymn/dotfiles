#!/usr/bin/python3 -I
"""Attention budget: keep the rules agents must remember by themselves within a fixed size.

An attention item is a rule an agent has to remember and apply on its own, with nothing
automatic (hook, lint, test, CI, a script that is the only way to do the step) enforcing it.
The budget file (~/.claude/attention/budget.json) holds:

- caps: the most always-on attention items each role may carry;
- registers: JSON files listing those items ({"items": [{"id", "role", "rule", "why", "source"}]}).
  ~/.claude/attention/items.json is the global register every session carries; every other
  register belongs to one session or project. The cap applies to global + one other register,
  so concurrent sessions do not share a budget. Role "all" counts against every role;
- prose: instruction files agents load, each with a byte cap that can only go down.

Usage:
  attention-budget.py status          print usage against the caps
  attention-budget.py ratchet         lower each prose cap to the file's current size
  attention-budget.py pre             PreToolUse hook (Edit/Write/MultiEdit)

pre denies an Edit/Write/MultiEdit that would raise or remove a cap, drop a register or prose
entry whose file still exists, put a role over its cap, grow a prose file past its cap, edit
this script, or remove this hook from settings.json. Shell commands are not checked: the
budget guards against drift in the files agents edit, not a session set on bypassing it.
Raising a cap is never allowed from a session.
"""
import json
import os
import sys

BUDGET = os.path.expanduser("~/.claude/attention/budget.json")
GLOBAL_REGISTER = os.path.expanduser("~/.claude/attention/items.json")
SETTINGS = os.path.expanduser("~/.claude/settings.json")
HOOK_MARK = "attention-budget.py"
# Every instruction file in these directories needs a prose cap, so splitting a file cannot move text out of the budget.
CAPPED_DIRS = ["~/.claude/skills/hiden", "~/.claude/skills/toolchain", "~/.claude/skills/public-text", "~/.claude/skills/wasure"]


def in_capped_dir(path):
    return path.endswith(".md") and any(path.startswith(expand(d) + os.sep) for d in CAPPED_DIRS)


def expand(path):
    return os.path.realpath(os.path.expanduser(path))


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def load_budget(text=None):
    data = json.loads(text if text is not None else read(BUDGET))
    data.setdefault("caps", {})
    data.setdefault("registers", [])
    data.setdefault("prose", {})
    return data


def load_items(text):
    if text is None:
        return []
    items = json.loads(text).get("items", [])
    for item in items:
        for key in ("id", "role", "rule", "why", "source"):
            if not str(item.get(key, "")).strip():
                raise ValueError(f"item {item.get('id', '?')} lacks {key}")
    return items


def role_counts(items, caps):
    out = {}
    for item in items:
        roles = caps.keys() if item["role"] == "all" else [item["role"]]
        for role in roles:
            out[role] = out.get(role, 0) + 1
    return out


def scopes(budget, override=None):
    """Yield (label, per-role counts) for global alone and global + each other register."""
    override = override or {}
    g = expand(GLOBAL_REGISTER)
    global_items = load_items(override.get(g, read(g)))
    yield "global", role_counts(global_items, budget["caps"])
    for reg in budget["registers"]:
        path = expand(reg)
        if path == g:
            continue
        items = load_items(override.get(path, read(path)))
        if items:
            yield path, role_counts(global_items + items, budget["caps"])


def tracked(budget):
    regs = {expand(r) for r in budget["registers"]} | {expand(GLOBAL_REGISTER)}
    prose = {expand(p): cap for p, cap in budget["prose"].items()}
    return regs, prose


def violations(budget, override=None):
    out = []
    override = override or {}
    for label, per_role in scopes(budget, override):
        for role, n in sorted(per_role.items()):
            cap = budget["caps"].get(role)
            if cap is None:
                out.append(f"role '{role}' has no cap in budget.json")
            elif n > cap:
                where = "the global register" if label == "global" else f"global + {label}"
                out.append(f"role '{role}' carries {n} attention items in {where}; the cap is {cap}")
    _, prose = tracked(budget)
    found = {os.path.join(r, n) for d in CAPPED_DIRS for r, _, fs in os.walk(expand(d)) for n in fs}
    found |= {p for p, text in override.items() if text is not None}  # a Write about to create the file
    for path in sorted(p for p in found if in_capped_dir(p) and p not in prose):
        out.append(f"{path} has no prose cap in budget.json: add one, or fold the text into a capped file")
    for path, cap in sorted(prose.items()):
        text = override.get(path, read(path))
        size = len(text.encode("utf-8")) if text is not None else 0
        if size > cap:
            out.append(f"{path} is {size} bytes; the cap is {cap}")
    return out


def budget_change_errors(old, new):
    """Ways new budget.json loosens old: raised/removed caps, dropped live entries."""
    out = []
    for role, cap in old["caps"].items():
        if new["caps"].get(role, 10**9) > cap:
            out.append(f"the cap of '{role}' cannot be raised or removed ({cap})")
    new_regs = {expand(r) for r in new["registers"]}
    for reg in old["registers"]:
        if expand(reg) not in new_regs and read(expand(reg)) is not None:
            out.append(f"register {reg} cannot be dropped while its file exists")
    new_prose = {expand(k): v for k, v in new["prose"].items()}
    for p, cap in old["prose"].items():
        newcap = new_prose.get(expand(p))
        if newcap is None and read(expand(p)) is None:
            continue
        if newcap is None or newcap > cap:
            out.append(f"the prose cap of {p} cannot be raised or removed ({cap})")
    return out


def short(path):
    return path.replace(os.path.expanduser("~"), "~")


def status():
    budget = load_budget()
    print("attention items (always-on, by role; global + one session register):")
    for label, per_role in scopes(budget):
        usage = ", ".join(f"{r} {per_role.get(r, 0)}/{c}" for r, c in sorted(budget["caps"].items()))
        print(f"  {'global' if label == 'global' else short(label)}: {usage}")
    print("instruction prose (bytes / cap):")
    _, prose = tracked(budget)
    for path, cap in sorted(prose.items()):
        text = read(path)
        size = len(text.encode("utf-8")) if text is not None else 0
        print(f"  {size}/{cap}  {short(path)}")
    bad = violations(budget)
    for v in bad:
        print(f"OVER: {v}")
    return 1 if bad else 0


def ratchet():
    budget = load_budget()
    changed = False
    for path, cap in list(budget["prose"].items()):
        text = read(expand(path))
        size = len(text.encode("utf-8")) if text is not None else 0
        if size < cap:
            budget["prose"][path] = size
            changed = True
    if changed:
        write(BUDGET, json.dumps(budget, ensure_ascii=False, indent=2) + "\n")
    return status()


def new_text(tool, inp, path):
    if tool == "Write":
        return inp.get("content", "")
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    text = read(path) or ""
    for e in edits:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


ADVICE = (" Mechanize a rule (hook, lint, test, script) or replace an existing one instead of"
          " adding attention. Run `~/.claude/hooks/attention-budget.py status` to see usage.")


def deny(reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "Attention budget: " + reason + ADVICE,
    }}, sys.stdout)
    return 0


def edit_errors(budget, path, text):
    """Errors if path were replaced by text (None when the edit is fine)."""
    if path == expand(__file__):
        return ["this hook enforces the budget; only the owner edits it"]
    if path == expand(SETTINGS):
        return None if HOOK_MARK in (text or "") else [
            "settings.json must keep the attention-budget hooks; only the owner removes them"]
    if path == expand(BUDGET):
        try:
            new = load_budget(text)
        except (ValueError, KeyError, TypeError) as e:
            return [f"budget.json would not parse ({e})"]
        return budget_change_errors(budget, new) or violations(new) or None
    regs, prose = tracked(budget)
    if path not in regs and path not in prose and not in_capped_dir(path):
        return None
    try:
        return violations(budget, {path: text}) or None
    except (ValueError, KeyError, TypeError) as e:
        return [f"{path} would not parse ({e})"]


def pre():
    event = json.load(sys.stdin)
    tool = event.get("tool_name", "")
    inp = event.get("tool_input", {}) or {}
    if tool not in ("Edit", "Write", "MultiEdit") or read(BUDGET) is None:
        return 0
    budget = load_budget()
    path = expand(inp.get("file_path", ""))
    errors = edit_errors(budget, path, new_text(tool, inp, path))
    return deny("; ".join(errors) + ".") if errors else 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    if mode == "hook":
        mode = "pre"
    sys.exit({"status": status, "ratchet": ratchet, "pre": pre}[mode]())
