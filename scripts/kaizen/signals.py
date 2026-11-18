#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Signals of a kaizen change, counted from Claude Code transcripts (docs/kaizen.md §5, post-merge observation).

regression: the regression-test unit. Worker sessions are subagents/**/*.meta.json with agentType "opus-worker" under
the projects root; the transcript is the agent-<id>.jsonl beside each. Only records whose timestamp lies in the window
count.
  - opportunity: one per worker that made a successful Edit/Write/MultiEdit (tool_use joined to its tool_result by id)
    that the hook's own matcher (matching_unit of home/dot_claude/hooks/executable_orchestration-context.py) treats as
    a chance to deliver the unit.
  - counted: after the write, Bash results show a test the worker wrote failing (a FAIL line naming it, and no
    import, syntax, collection or compile error in the output) and that same test passing, in either order (green
    with the fix, then red on a copy with it removed, shows the same thing as red first, then green).
  - ambiguous: a red for the intended reason and a green were seen, but not for the same written test.
  - deliveries: hook_additional_context attachments holding the unit text.
  - harm: median assistant turns (API responses) and final report length (the last SubagentHandback message, else
    the last assistant text) for workers with and without an opportunity.
The patterns are coarse (regex over tool output); --examples prints source lines to read by hand. Prints to stdout
only and writes nothing.
"""
import argparse
import importlib.util
import json
import os
import re
import shlex
import statistics
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "home/dot_claude/hooks/executable_orchestration-context.py"
UNIT_ID = "regression-seen-fail"
WRITE_TOOLS = ("Edit", "Write", "MultiEdit")
TRUNCATE = 160

# Test names a write defines.
NAME_PATTERNS = (
    re.compile(r"\bfunc\s+(Test\w+)\s*\("),  # Go
    re.compile(r"\bdef\s+(test\w*)\s*\("),  # Python
    re.compile(r"#\[(?:\w+::)*test\b[^\]]*\]\s*(?:#\[[^\]]*\]\s*)*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)"),  # Rust
    re.compile(r"\b(?:it|test)(?:\.(?:only|concurrent|skip|todo))*\(\s*(['\"`])((?:(?!\1).)+)\1"),  # JS/TS
)
# Output that rules a red out: the test did not get to assert anything.
ERROR = re.compile(
    r"ImportError|ModuleNotFoundError|SyntaxError|IndentationError|NameError|ReferenceError|ERROR collecting"
    r"|errors? during collection|error\[E\d+\]|could not compile|\[build failed\]|\[setup failed\]"
    r"|Cannot find module|Failed to resolve import|Failed to load url|error TS\d+|is not a function|is not defined"
    r"|\bundefined: \w|cannot find (?:package|module)|Transform failed")
FAIL_LINE = re.compile(r"--- FAIL|\bFAIL(?:ED|S)?\b|\bfailed\b|×|✕|✖|✗|●|panicked|\bERROR\b")
PASS_LINE = re.compile(r"--- PASS|\bPASS(?:ED)?\b|✓|✔|√|\.\.\. ok\b|\bok\s*$")
# A failed run whose failing test is not named; a symbol or a bare FAIL counts only at the start of a line, so source
# code and other tools' output (a FAIL constant, a "×" in a comment) do not.
FAIL_ANY = re.compile(r"--- FAIL|\bFAILED\b|^\W*(?:\d+[:-]\s*)?FAIL\b|\b[1-9]\d* failed\b(?!\s*\d)|panicked at"
                      r"|test result: FAILED|ℹ fail [1-9]", re.M)
NOT_CLEAN = re.compile(r"^\W*(?:\d+[:-]\s*)?[×✕✖]\s", re.M)
PASS_SUMMARY = re.compile(r"\b\d+ passed\b|^OK\b|^ok\s+\S|test result: ok\.|^\s*PASS\b|ℹ pass [1-9]", re.M)
OPERATOR_CHARS = "();<>|&\n"
SHELLS = frozenset(("sh", "bash", "zsh", "dash"))
WRAPPERS = frozenset(("env", "time", "nice", "nohup", "command", "exec", "sudo", "timeout"))
# Programs that only show, filter or store text: a command of these alone replays output and runs no test.
VIEWERS = frozenset("cat bat less more head tail echo printf sed awk grep egrep fgrep rg ag jq yq ls pwd cd wc sort "
                    "uniq cut tr diff nl column tee true false sleep git".split())
FILTER_OPTIONS = {"pytest": ("-k",), "unittest": ("-k",), "go": ("-run", "--run", "-test.run"),
                  "js": ("-t", "--testNamePattern")}
VALUE_OPTIONS = {"pytest": frozenset(("-m", "-p", "-c", "-o", "-W", "-n", "--deselect", "--ignore", "--ignore-glob",
                                      "--rootdir", "--confcutdir", "--basetemp", "--maxfail", "--durations",
                                      "--junitxml", "--tb"))}


def load_hook(path=HOOK):
    """The hook module, loaded from the checkout so a chance to deliver means what the hook means."""
    spec = importlib.util.spec_from_file_location("orchestration_context", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def timestamp(record):
    try:
        t = datetime.fromisoformat(record["timestamp"])
    except (KeyError, TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def names_in(text):
    found = []
    for pattern in NAME_PATTERNS:
        for m in pattern.finditer(text):
            name = m.group(m.lastindex)
            if name.strip() and name not in found:
                found.append(name)
    return found


def written_names(tool, tool_input, result):
    """Names of the tests a successful write defines or edits (the enclosing test when an Edit shows none)."""
    string = lambda v: v if isinstance(v, str) else ""
    if tool == "Write":
        return names_in(string(tool_input.get("content")))
    edits = tool_input.get("edits") if tool == "MultiEdit" else [tool_input]
    original = string(result.get("originalFile")) if isinstance(result, dict) else ""
    names = []
    for e in edits if isinstance(edits, list) else []:
        if not isinstance(e, dict):
            continue
        new, old = string(e.get("new_string")), string(e.get("old_string"))
        found = names_in(new)
        if not found and old and old in original:
            found = names_in(original[:original.index(old)])[-1:]
        names += [n for n in found if n not in names]
    return names


def mentions(line, name):
    if re.fullmatch(r"\w+", name):
        return re.search(rf"(?<!\w){re.escape(name)}(?!\w)", line) is not None
    return name in line


def simple_commands(command):
    """Word lists of the simple commands in a shell command line: comments and redirection targets dropped, the
    string of `sh -c` (bash, zsh) expanded in place."""
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=OPERATOR_CHARS)
        lex.whitespace, lex.whitespace_split, lex.commenters = " \t\r", True, ""
        tokens = list(lex)
    except ValueError:  # an unbalanced quote
        tokens = command.split()
    out, words, comment, redirect = [], [], False, False
    for tok in tokens + ["\n"]:
        if tok and set(tok) <= set(OPERATOR_CHARS):
            comment = comment and "\n" not in tok
            if "<" in tok or ">" in tok:
                redirect = True
                if words and words[-1].isdigit():  # the 2 of 2>&1
                    words.pop()
            elif words:
                out.append(words)
                words = []
        elif redirect:
            redirect = False
        elif comment or tok.startswith("#"):
            comment = True
        else:
            words.append(tok)
    expanded = []
    for w in out:
        p = program(w)
        flag = next((i for i, a in enumerate(p[1:2], 1) if re.fullmatch(r"-\w*c\w*", a)), None)
        if p and os.path.basename(p[0]) in SHELLS and flag and flag + 1 < len(p):
            expanded += simple_commands(p[flag + 1])
        else:
            expanded.append(w)
    return expanded


def program(words):
    """The words from the program on: variable assignments and wrappers (env, time, timeout 60) skipped."""
    i = 0
    while i < len(words):
        base = os.path.basename(words[i])
        if re.fullmatch(r"[A-Za-z_]\w*=.*", words[i], re.S):
            i += 1
        elif base in WRAPPERS:
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 1
            i += base == "timeout"  # its duration
        else:
            break
    return words[i:]


def is_test_run(command):
    """Whether the command runs anything but programs that only show text (cat of a saved log is a replay)."""
    return any(p and os.path.basename(p[0]) not in VIEWERS for p in map(program, simple_commands(command)))


def python_target(arg, kind):
    """(module, class, test) a pytest or unittest argument selects, None where it does not narrow; None when the
    argument names no Python module (a directory, a marker)."""
    path, _, node = arg.partition("::")
    if path.endswith(".py"):
        parts = [re.sub(r"\[.*", "", p) for p in node.split("::")] if node else []
        if parts and parts[-1][:1].isupper():
            return Path(path).stem, parts[-1], None
        return Path(path).stem, (parts[-2] if len(parts) > 1 else "") if parts else None, parts[-1] if parts else None
    if kind != "unittest" or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", arg):
        return None
    parts = arg.split(".")
    c = next((i for i, p in enumerate(parts) if p[:1].isupper()), None)
    if c is None:
        return parts[-1], None, None
    return (parts[c - 1] if c else None), parts[c], (parts[c + 1] if c + 1 < len(parts) else None)


def runners(command):
    """(kind, name filters, Python targets) of each test runner in the command: pytest and unittest (-k), go test
    (-run), jest and vitest (-t, --testNamePattern)."""
    out = []
    for words in map(program, simple_commands(command)):
        base = [os.path.basename(w) for w in words]
        if "-m" in words[:-1] and words[words.index("-m") + 1] in ("pytest", "unittest"):
            kind, args = words[words.index("-m") + 1], words[words.index("-m") + 2:]
        elif {"pytest", "py.test"} & set(base):
            kind, args = "pytest", words[next(i for i, b in enumerate(base) if b in ("pytest", "py.test")) + 1:]
        elif base[:2] == ["go", "test"]:
            kind, args = "go", words[2:]
        elif {"jest", "vitest"} & set(base):
            kind, args = "js", words[next(i for i, b in enumerate(base) if b in ("jest", "vitest")) + 1:]
        else:
            continue
        filters, targets, it = [], [], iter(args)
        if kind == "unittest" and args[:1] == ["discover"]:
            it = iter([])
        for a in it:
            opt = next((o for o in FILTER_OPTIONS[kind] if a == o or a.startswith(o + "=")
                        or (len(o) == 2 and a.startswith(o))), None)
            if opt:
                filters.append(next(it, "") if a == opt else a[len(opt):].removeprefix("="))
            elif a in VALUE_OPTIONS.get(kind, ()):
                next(it, None)
            elif not a.startswith("-") and kind in ("pytest", "unittest") and (t := python_target(a, kind)):
                targets.append(t)
        out.append((kind, filters, targets))
    return out


def admits(kind, pattern, module, cls, name):
    """Whether a name filter keeps the test (an unparsable one does not)."""
    try:
        if kind == "go":
            return re.search(pattern.split("/")[0], name) is not None
        if kind == "js":
            return re.search(pattern, name) is not None
    except re.error:
        return False
    hay = [h.lower() for h in (module, cls, name, ".".join(p for p in (module, cls, name) if p)) if h]
    words = re.findall(r"\(|\)|[^\s()]+", pattern)
    expr = " ".join(w if w in ("and", "or", "not", "(", ")") else
                    str(any(fnmatchcase(h, w.lower() if "*" in w else f"*{w.lower()}*") for h in hay)) for w in words)
    try:
        return bool(words) and bool(eval(expr, {"__builtins__": {}}))  # only True, False, and, or, not, parentheses
    except SyntaxError:
        return False


def selects(target, module, cls, name):
    m, c, n = target
    return m == module and (c is None or cls is None or c == cls) and (n is None or n == name)


def selections(command, module, name, cls=None):
    """Classes under which the command's runners evidently ran the test, from a target naming its module, class or
    test (None: the target does not narrow by class), [] when no target selects it or a filter (-k, -run, -t) leaves
    it out, or None when no runner names Python targets, so its selection is unknown."""
    found, unknown, found_runners = [], False, runners(command)
    for kind, filters, targets in found_runners:
        if not all(admits(kind, f, module, cls, name) for f in filters):
            continue
        if not targets:
            unknown = True
        found += [t[1] for t in targets if selects(t, module, cls, name)]
    return found or (None if unknown or not found_runners else [])


def qualifiers(line, name):
    """(module, class) a result line gives for the test: unittest "name (module.Class.name)", pytest
    "path.py::Class::name" ("" for no class); None where the line gives none."""
    m = re.search(rf"(?<!\w){re.escape(name)} \(([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\)", line)
    if m:
        parts = m.group(1).split(".")
        parts = parts[:-1] if parts[-1] == name else parts
        return (parts[-2], parts[-1]) if len(parts) > 1 else (None, None)
    m = re.search(rf"([\w./-]+)\.py::((?:\w+::)*){re.escape(name)}(?!\w)", line)
    if m:
        classes = [c for c in m.group(2).split("::") if c]
        return Path(m.group(1)).name, classes[-1] if classes else ""
    return None, None


def compatible(a, b):
    return all(x is None or y is None or x == y for x, y in zip(a, b))


def references(output, command, name, file_path):
    """Whether a clean pass ran this test: its name, its file, a relative directory above the file in the command,
    or (Go, Rust) its package or target is named."""
    hay = f"{command}\n{output}"
    p = Path(file_path)
    if mentions(hay, name) or p.name in hay:
        return True
    for token in re.split(r"[\s;&|()'\"=]+", command):
        token = token.removeprefix("./").rstrip("/")
        if not token.startswith(("/", ".", "~", "$")) and re.search(r"[A-Za-z]", token) and f"/{token}/" in file_path:
            return True
    if p.suffix == ".go":
        return re.search(rf"(?:^|[\s/]){re.escape(p.parent.name)}(?:/|\s|$)", hay, re.M) is not None
    if p.suffix == ".rs":
        return re.search(rf"--test[ =]{re.escape(p.stem)}\b", hay) is not None
    return False


def classify(output, command, idents):
    """Reds and greens in one Bash result: lists of (line index, test name or None, (module, class), line)."""
    lines = output.splitlines()
    error = ERROR.search(output) is not None
    reds, greens = [], []
    for name, file_path in idents.items():
        for i, line in enumerate(lines):
            if not mentions(line, name):
                continue
            quals = qualifiers(line, name)
            if quals[0] not in (None, Path(file_path).stem):
                continue  # a test of the same name in another file
            rest = line.replace(name, " ")
            if FAIL_LINE.search(rest):
                if not error and not re.search(r"\bERROR\b", rest):
                    reds.append((i, name, quals, line))
            elif PASS_LINE.search(rest) and not error:
                greens.append((i, name, quals, line))
    fail_any = FAIL_ANY.search(output)
    if fail_any and not error and not reds:
        i = output[:fail_any.start()].count("\n")
        reds.append((i, None, (None, None), lines[i]))
    summary = PASS_SUMMARY.search(output)
    if summary and not fail_any and not NOT_CLEAN.search(output) and not error:
        i = output[:summary.start()].count("\n")
        named = []
        for name, file_path in idents.items():
            classes = selections(command, Path(file_path).stem, name)
            if classes is None:
                classes = [None] if references(output, command, name, file_path) else []
            named += [(i, name, (None, c), lines[i]) for c in classes]
        greens += named or [(i, None, (None, None), lines[i])]
    return reds, greens


class Worker:
    def __init__(self, path):
        self.path = path
        self.in_window = False
        self.opportunity = None  # (line number, timestamp, file path)
        self.idents = {}  # test name -> file it was written to
        self.reds, self.greens = [], []  # (line number, line index, name, (module, class), line)
        self.deliveries = []  # line numbers
        self.messages = []  # assistant message ids, in order
        self.texts = {}  # message id -> text
        self.handback = None  # the last SubagentHandback message, the report of a background worker
        self.bad_lines = 0
        self.result = None  # outcome(), set once the scan is complete

    @property
    def turns(self):
        return len(self.messages)

    @property
    def report_chars(self):
        if self.handback is not None:
            return len(self.handback)
        with_text = [m for m in self.messages if self.texts.get(m)]
        return len(self.texts[with_text[-1]]) if with_text else 0

    def outcome(self):
        """("counted"|"ambiguous"|"not counted", evidence)."""
        for r in self.reds:
            if r[2] is None:
                continue
            for g in self.greens:
                if g[2] == r[2] and compatible(r[3], g[3]):
                    return "counted", (r, g)
        if self.reds and self.greens:
            return "ambiguous", (self.reds[0], self.greens[0])
        reason = "red without a green" if self.reds else "no red for an intended reason after the write"
        return "not counted", reason


def scan(path, unit, hook, since, until):
    w = Worker(path)
    uses = {}
    with open(path, encoding="utf-8") as f:
        for number, raw in enumerate(f, 1):
            try:
                d = json.loads(raw)
            except ValueError:
                w.bad_lines += 1
                continue
            if not isinstance(d, dict):
                w.bad_lines += 1
                continue
            t = timestamp(d)
            if t is None or not since <= t <= until:
                continue
            w.in_window = True
            kind, message = d.get("type"), d.get("message") if isinstance(d.get("message"), dict) else {}
            content = message.get("content")
            if kind == "assistant" and isinstance(content, list):
                mid = message.get("id") or d.get("uuid") or f"line-{number}"
                if mid not in w.texts:
                    w.messages.append(mid)
                    w.texts[mid] = ""
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and isinstance(b.get("text"), str):
                        w.texts[mid] += b["text"]
                    elif b.get("type") == "tool_use" and isinstance(b.get("id"), str):
                        if b.get("name") == "SubagentHandback" and isinstance((b.get("input") or {}).get("message"), str):
                            w.handback = b["input"]["message"]
                        uses[b["id"]] = (b.get("name"), b.get("input") if isinstance(b.get("input"), dict) else {},
                                         d.get("cwd"))
            elif kind == "user" and isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in uses:
                        tool_result(w, number, t, uses[b["tool_use_id"]], b, d.get("toolUseResult"), unit, hook)
            elif kind == "attachment":
                a = d.get("attachment") if isinstance(d.get("attachment"), dict) else {}
                body = a.get("content")
                body = body if isinstance(body, list) else [body]
                if a.get("type") == "hook_additional_context" and any(
                        isinstance(c, str) and unit["text"] in c for c in body):
                    w.deliveries.append(number)
    return w


def tool_result(w, number, t, use, block, result, unit, hook):
    tool, tool_input, cwd = use
    if block.get("is_error"):
        return
    if tool in WRITE_TOOLS:
        data = {"tool_name": tool, "tool_input": tool_input, "agent_type": unit["agent_type"], "cwd": cwd}
        if cwd and hook.matching_unit([unit], data):
            if w.opportunity is None:
                w.opportunity = (number, t, tool_input["file_path"])
            for name in written_names(tool, tool_input, result):
                w.idents.setdefault(name, tool_input["file_path"])
    elif tool == "Bash" and w.opportunity is not None and is_test_run(str(tool_input.get("command") or "")):
        reds, greens = classify(text_of(block.get("content")), str(tool_input.get("command") or ""), w.idents)
        w.reds += [(number, *r) for r in reds]
        w.greens += [(number, *g) for g in greens]


def rate(numerator, denominator):
    return round(numerator / denominator, 3) if denominator else None


def median(values):
    return statistics.median(values) if values else None


def cut(line):
    line = line.strip()
    return line if len(line) <= TRUNCATE else line[:TRUNCATE - 1] + "…"


def regression(projects, days=30, now=None, hook_path=HOOK, unit_id=UNIT_ID, examples=0):
    hook = load_hook(hook_path)
    unit = next(u for u in hook.load_units() if u.get("id") == unit_id)
    until = now or datetime.now(timezone.utc)
    since = until - timedelta(days=days)
    traces = {"missing": 0, "unreadable": 0, "unreadable_meta": 0, "bad_lines": 0}
    workers = []
    for meta in sorted(Path(projects).glob("*/*/subagents/**/*.meta.json")):
        try:
            recent = since.timestamp() <= meta.stat().st_mtime
        except OSError:
            continue
        try:
            agent_type = json.loads(meta.read_text(encoding="utf-8")).get("agentType")
        except (OSError, ValueError, AttributeError):
            traces["unreadable_meta"] += recent
            continue
        if agent_type != unit["agent_type"]:
            continue
        transcript = meta.with_name(meta.name.removesuffix(".meta.json") + ".jsonl")
        if not transcript.exists():
            traces["missing"] += recent
            continue
        try:
            w = scan(transcript, unit, hook, since, until)
        except (OSError, UnicodeDecodeError):
            traces["unreadable"] += recent
            continue
        traces["bad_lines"] += w.bad_lines
        if w.in_window:
            workers.append(w)

    with_opp = [w for w in workers if w.opportunity]
    by_kind = {"counted": [], "ambiguous": [], "not counted": []}
    for w in with_opp:
        w.result = w.outcome()
        by_kind[w.result[0]].append(w)
    counted, ambiguous = by_kind["counted"], by_kind["ambiguous"]
    delivered = [w for w in with_opp if w.deliveries]
    group = lambda ws: {"workers": len(ws), "median_turns": median([w.turns for w in ws]),
                        "median_report_chars": median([w.report_chars for w in ws])}
    out = {
        "signal": "regression",
        "unit": unit_id,
        "window": {"days": days, "since": since.isoformat(), "until": until.isoformat()},
        "workers": len(workers),
        "opportunities": len(with_opp),
        "counted": len(counted),
        "ambiguous": len(ambiguous),
        "not_counted": len(by_kind["not counted"]),
        "rate": rate(len(counted), len(with_opp)),
        "deliveries": {
            "attachments": sum(len(w.deliveries) for w in workers),
            "workers": sum(1 for w in workers if w.deliveries),
            "opportunities_delivered": len(delivered),
            "opportunities_missed": len(with_opp) - len(delivered),
            "duplicated": sum(1 for w in workers if len(w.deliveries) > 1),
            "rate": rate(len(delivered), len(with_opp)),
        },
        "harm": {"with_opportunity": group(with_opp),
                 "without_opportunity": group([w for w in workers if not w.opportunity])},
        "traces": traces,
    }
    if examples:
        recent = lambda ws: sorted(ws, key=lambda w: w.opportunity[1], reverse=True)[:examples]
        out["examples"] = {kind.replace(" ", "_"): [evidence(w) for w in recent(ws)] for kind, ws in by_kind.items()}
    return out


def evidence(w):
    kind, detail = w.result
    write = f"{w.path}:{w.opportunity[0]}: wrote {cut(w.opportunity[2])}"
    if kind == "not counted":
        return {"write": write, "reason": detail}
    (rn, _, rname, _, rline), (gn, _, gname, _, gline) = detail
    return {"write": write, "red": f"{w.path}:{rn}: {cut(rline)}", "green": f"{w.path}:{gn}: {cut(gline)}",
            "test": rname or gname}


def render(out):
    lines = [f"regression ({out['window']['days']} days to {out['window']['until']}): {out['workers']} workers, "
             f"{out['opportunities']} opportunities, {out['counted']} counted, {out['ambiguous']} ambiguous, "
             f"{out['not_counted']} not counted; rate {'n/a (no opportunities)' if out['rate'] is None else out['rate']}"]
    d = out["deliveries"]
    lines.append(f"deliveries: {d['attachments']} attachments in {d['workers']} workers; "
                 f"{d['opportunities_delivered']} of {out['opportunities']} opportunities delivered, "
                 f"{d['duplicated']} workers with more than one")
    for k, g in out["harm"].items():
        lines.append(f"{k}: {g['workers']} workers, median turns {g['median_turns']}, "
                     f"median report chars {g['median_report_chars']}")
    lines.append("traces: " + ", ".join(f"{k} {v}" for k, v in out["traces"].items()))
    for kind, cases in out.get("examples", {}).items():
        for case in cases:
            lines.append(f"[{kind}]" + (f" test {case['test']!r}" if case.get("test") else f" {case.get('reason')}"))
            lines += [f"  {case[k]}" for k in ("write", "red", "green") if k in case]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="signal", required=True)
    p = sub.add_parser("regression", help="the regression-test unit")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--json", action="store_true")
    p.add_argument("--examples", type=int, default=0, help="cases of each kind to print with transcript file:line")
    p.add_argument("--projects", default=os.path.expanduser("~/.claude/projects"), help="Claude Code projects root")
    p.add_argument("--hook", default=str(HOOK), help="the orchestration-context hook whose matcher defines a chance")
    p.add_argument("--unit", default=UNIT_ID)
    args = parser.parse_args(argv)
    out = regression(args.projects, args.days, hook_path=args.hook, unit_id=args.unit, examples=args.examples)
    print(json.dumps(out, indent=2, ensure_ascii=False) if args.json else render(out))


if __name__ == "__main__":
    main()
