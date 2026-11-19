"""Observation of the kaizen daily cycle (docs/kaizen.md §6): evidence from a fixed window, recomputed every run.

Nothing here writes. observe() counts each source's observations in [since, until) and returns one result; a source
that fails is marked "fail" with its error and the others still run. Only regular files are opened (lstat, so a symlink,
FIFO or device is listed as unreadable rather than read).
  transcripts  parent and subagent *.jsonl under the projects root whose mtime is in the window; only complete lines
               are read (an unterminated last line is still being written and is skipped). Owner utterances of a
               session that T3 Code did not run are typed user records with origin.kind "human"; those of a T3 session
               come only from the T3 database (its transcript cannot tell them from injected input).
  t3           the T3 Code state database opened read-only. Owner = role user, createdBy user, creationSource web or
               mobile, in a root thread; compaction and agent rows are synthetic; other user rows are unknown.
  codex        rollout-*.jsonl under the Codex sessions root: sessions started in the window, per cwd.
  ledgers      lines that record a miss (見逃し) in the review ledgers, dated by a day in Asia/Tokyo whose start lies in
               the window.
  gh           for the repositories most worked in (by the cwd of transcripts and Codex sessions): merged reverts, merged
               PRs that fix another merged PR of the same repository, failed runs on the default branch.
Signals: owner-reply (an owner utterance of at most 300 characters after an assistant turn, not the first of its
session: an unlabelled candidate to read by hand), revert, fix-pr, ci-fail-main, ledger-miss (misses); meta-effort,
hiden-in-worker, reference-unread (waste). No model is called.
"""
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

EXCERPT = 160
SHORT_REPLY = 300
GH_REPOS = 10
GH_TIMEOUT = 60
SIGNALS = {"owner-reply": "miss", "revert": "miss", "fix-pr": "miss", "ci-fail-main": "miss", "ledger-miss": "miss",
           "meta-effort": "waste", "hiden-in-worker": "waste", "reference-unread": "waste"}
META_NAMES = ("review-ledgers/", "retro.md", "attention/budget.json", "attention-budget.py")
REFERENCE = re.compile(r"skills/hiden/references/([\w.-]+\.md)")
GITHUB = re.compile(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")
ONE_REF = r"(?:\b[\w.-]+/[\w.-]+)?#\d+"
FIX_CLAUSE = re.compile(rf"\bfix(?:es|ed)?\b[^#\n]{{0,60}}?({ONE_REF}(?:[ \t]*(?:,|\band\b|\bor\b|&)?[ \t]*"
                        rf"(?:fix(?:es|ed)?[ \t]+)?{ONE_REF})*)", re.I)
FIX_REF = re.compile(r"(?:\b([\w.-]+/[\w.-]+))?#(\d+)")
LEDGER_LINE = re.compile(r"^\s*-\s*(\d{4}-\d{2}-\d{2})\b")
NO_MISS = re.compile(r"見逃し\s*(?:0|なし|無し)")
OWNER_SOURCES = ("web", "mobile")
TZ = ZoneInfo("Asia/Tokyo")  # the owner's day: ledger dates and the run date
# byte patterns that decide whether a transcript line is parsed at all
T3_ENTRY = re.compile(rb'"entrypoint":\s*"t3-code"')
USER, ASSISTANT = re.compile(rb'"type":\s*"user"'), re.compile(rb'"type":\s*"assistant"')
TOOL_USE, TOOL_RESULT = re.compile(rb'"type":\s*"tool_use"'), re.compile(rb'"tool_use_id"')


def iso(t):
    return t.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value):
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def cut(text, n=EXCERPT):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 1] + "…"


def item(signal, where, excerpt, ts, provenance="synthetic", repo=None):
    return {"id": hashlib.sha1(f"{signal}\0{where}".encode()).hexdigest()[:12], "signal": signal,
            "kind": SIGNALS[signal], "where": where, "excerpt": cut(excerpt), "provenance": provenance, "repo": repo,
            "ts": iso(ts) if isinstance(ts, datetime) else ts}


def run(argv, timeout, **kw):
    """subprocess.run with its own timeout (the child is killed when it passes)."""
    return subprocess.run(argv, timeout=timeout, capture_output=True, text=True, **kw)


def regular(path):
    """os.lstat of path; OSError unless it is a regular file. A FIFO, device or symlink is never opened (opening a
    FIFO blocks until a writer appears)."""
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode):
        raise OSError(f"{path}: not a regular file")
    return st


def complete_lines(path):
    """The lines of a file that end in a newline, as bytes; an unterminated last line is left out."""
    return path.read_bytes().split(b"\n")[:-1]


class Source:
    def __init__(self, name):
        self.name, self.files, self.records, self.bad_lines = name, 0, 0, 0
        self.unreadable, self.error, self.status = [], None, "ok"
        self.started = time.monotonic()

    def summary(self):
        if self.status == "ok" and self.unreadable:
            self.status, self.error = "fail", f"{len(self.unreadable)} unreadable: {', '.join(self.unreadable[:5])}"
        out = {"status": self.status, "files": self.files, "records": self.records, "bad_lines": self.bad_lines,
               "secs": round(time.monotonic() - self.started, 2)}
        if self.error:
            out["error"] = cut(self.error, 300)
        return out


# ---------------------------------------------------------------- transcripts


def typed(record):
    """A user record shaped like typed input: string content, not meta, a summary, a tool result or a command."""
    content = (record.get("message") or {}).get("content")
    return (isinstance(content, str) and not record.get("isMeta") and not record.get("isCompactSummary")
            and "toolUseResult" not in record
            and not content.lstrip().startswith(("<command-", "<task-notification>", "<local-command")))


def scan_transcript(path, subagent, since, until, out, src):
    """Read one transcript into `out` (items, utterances, cwds, refs)."""
    lines = complete_lines(path)
    t3 = any(T3_ENTRY.search(line) for line in lines[:50])
    seen_user = seen_assistant = False
    meta, hiden, cwd = [], None, None
    for number, line in enumerate(lines, 1):
        is_user, is_assistant = USER.search(line), ASSISTANT.search(line)
        if is_assistant and not TOOL_USE.search(line):
            seen_assistant = True  # a text turn: nothing else to read from it
            continue
        if not (is_user or is_assistant) or (is_user and TOOL_RESULT.search(line)):
            continue  # other record types and tool results carry no signal here
        try:
            d = json.loads(line)
        except ValueError:
            src.bad_lines += 1
            continue
        if not isinstance(d, dict):
            src.bad_lines += 1
            continue
        src.records += 1
        t = parse_time(d.get("timestamp") or "")
        in_window = t is not None and since <= t < until
        cwd = cwd or d.get("cwd")
        message = d.get("message") if isinstance(d.get("message"), dict) else {}
        if d.get("type") == "user" and typed(d):
            human = (d.get("origin") or {}).get("kind") == "human"
            first = not seen_user
            seen_user = seen_user or human or t3
            if in_window and not subagent and not t3 and human:
                out["tally"]["owner"] += 1
                if len(message["content"]) <= SHORT_REPLY and not first and seen_assistant:
                    out["items"].append(item("owner-reply", f"{path}:{number}", message["content"], t, "owner"))
            elif in_window and not subagent and t3:
                out["t3_sessions"].add(path.stem)
        elif d.get("type") == "assistant" and isinstance(message.get("content"), list):
            seen_assistant = True
            if not in_window:
                continue
            for b in message["content"]:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                args = b.get("input") if isinstance(b.get("input"), dict) else {}
                blob = json.dumps(args, ensure_ascii=False)
                m = REFERENCE.search(str(args.get("file_path") or "")) if b.get("name") == "Read" else None
                if m and out["refs"].get(m.group(1), "") < iso(t):
                    out["refs"][m.group(1)] = iso(t)
                if any(n in blob for n in META_NAMES):
                    meta.append((number, t, f"{b.get('name')} {blob}"))
                if subagent and hiden is None and ((b.get("name") == "Skill" and args.get("skill") == "hiden")
                                                   or (b.get("name") == "Read" and "skills/hiden/" in blob)):
                    hiden = (number, t, f"{b.get('name')} {blob}")
    if meta:
        out["items"].append(item("meta-effort", f"{path}:{meta[0][0]}",
                                 f"{len(meta)} meta tool calls; first: {meta[0][2]}", meta[0][1]))
    if hiden:
        out["items"].append(item("hiden-in-worker", f"{path}:{hiden[0]}", hiden[2], hiden[1]))
    if cwd:
        out["cwds"][cwd] = out["cwds"].get(cwd, 0) + 1


def observe_transcripts(projects, since, until, out, src):
    floor = since.timestamp()
    for d, _, names in os.walk(projects, onerror=lambda e: src.unreadable.append(str(e.filename))):
        for name in names:
            path = Path(d, name)
            rel = path.relative_to(projects).parts
            if not name.endswith(".jsonl") or not (len(rel) == 2 or "subagents" in rel):
                continue
            try:
                if regular(path).st_mtime < floor:
                    continue
                src.files += 1
                scan_transcript(path, "subagents" in rel, since, until, out, src)
            except OSError as e:
                src.unreadable.append(f"{path}: {e.strerror or e}")


def reference_items(hiden, refs, now):
    folder = Path(hiden) / "references"
    return [item("reference-unread", str(p), f"references/{p.name} not read in the window", now)
            for p in sorted(folder.glob("*.md")) if p.name not in refs]


# ---------------------------------------------------------------- T3


def db_time(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def root_thread(payload):
    lineage = payload.get("lineage") if isinstance(payload, dict) else None
    return lineage is None or (isinstance(lineage, dict) and lineage.get("relationshipToParent") is None
                               and lineage.get("parentThreadId") is None)


def observe_t3(db, since, until, out, src):
    regular(db)
    src.files = 1
    # mode=ro still lets SQLite create the -wal and -shm files beside the database: they are its shared index that
    # every reader (the T3 app too) creates, holding no owner data. immutable=1 would avoid them but skip rows still
    # in the WAL. as_uri percent-encodes "#" and "?", which SQLite would read as fragment and query.
    conn = sqlite3.connect(Path(db).absolute().as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        roots = {tid for tid, payload in conn.execute(
            "select thread_id, payload_json from orchestration_v2_projection_threads")
            if root_thread(json.loads(payload))}
        rows = conn.execute(
            "select thread_id, created_at, payload_json from orchestration_v2_projection_messages "
            "where role = 'user' and created_at >= ? and created_at < ?", (db_time(since), db_time(until)))
        for thread, created, payload in rows.fetchall():
            src.records += 1
            try:
                d = json.loads(payload)
            except ValueError:
                src.bad_lines += 1
                continue
            text = d.get("text") if isinstance(d.get("text"), str) else ""
            if d.get("createdBy") != "user" or d.get("idleCompaction") is not None or text.lstrip().startswith(
                    "/compact"):
                out["tally"]["synthetic"] += 1
                continue
            if d.get("creationSource") not in OWNER_SOURCES or thread not in roots:
                out["tally"]["unknown"] += 1
                continue
            out["tally"]["owner"] += 1
            before, assistant = conn.execute(
                "select count(*), coalesce(sum(role = 'assistant'), 0) from orchestration_v2_projection_messages "
                "where thread_id = ? and created_at < ?", (thread, created)).fetchone()
            if len(text) <= SHORT_REPLY and before and assistant:
                out["items"].append(item("owner-reply", f"t3:{thread}:{d.get('id')}", text, parse_time(created),
                                         "owner"))
    finally:
        conn.close()


# ---------------------------------------------------------------- codex, ledgers, gh


def observe_codex(root, since, until, out, src):
    def fail(e):  # a missing or unreadable root fails the source rather than reading as no sessions
        raise e

    floor, counts = since.timestamp(), {}
    for d, _, names in os.walk(root, onerror=fail):
        for name in names:
            path = Path(d, name)
            if not (name.startswith("rollout-") and name.endswith(".jsonl")):
                continue
            try:
                if regular(path).st_mtime < floor:
                    continue
                with open(path, "rb") as f:
                    first = f.readline()
            except OSError as e:
                src.unreadable.append(f"{path}: {e.strerror or e}")
                continue
            src.files += 1
            try:
                d0 = json.loads(first)
                payload = d0["payload"]
                started = parse_time(payload.get("timestamp") or d0.get("timestamp"))
            except (ValueError, KeyError, TypeError, AttributeError):
                src.bad_lines += 1
                continue
            src.records += 1
            if started and since <= started < until:
                cwd = payload.get("cwd") or "?"
                counts[cwd] = counts.get(cwd, 0) + 1
                out["cwds"][cwd] = out["cwds"].get(cwd, 0) + 1
    out["codex_sessions"] = counts


def observe_ledgers(root, since, until, out, src):
    if not Path(root).is_dir():
        return
    for path in sorted(Path(root).glob("*.md")):
        src.files += 1
        try:
            regular(path)
            text = path.read_bytes().decode("utf-8", errors="replace")
        except OSError as e:
            src.unreadable.append(f"{path}: {e.strerror or e}")
            continue
        for number, line in enumerate(text.splitlines(), 1):
            src.records += 1
            m = LEDGER_LINE.match(line)
            if not m or "見逃し" not in line or NO_MISS.search(line):
                continue
            try:
                day = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=TZ)  # the start of that day
            except ValueError:
                continue
            if since <= day < until:
                out["items"].append(item("ledger-miss", f"{path}:{number}", line, m.group(1)))


def origin_repo(cwd):
    if not os.path.isdir(cwd):
        return None
    try:
        p = run(["git", "-C", cwd, "config", "--get", "remote.origin.url"], 10)
    except (OSError, subprocess.SubprocessError):
        return None
    m = GITHUB.search(p.stdout.strip()) if p.returncode == 0 else None
    return f"{m.group(1)}/{m.group(2)}" if m else None


def gh_json(gh, args):
    p = run([gh, *args], GH_TIMEOUT)
    if p.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])}: exit {p.returncode}: {p.stderr.strip()[:200]}")
    return json.loads(p.stdout or "null")


def observe_gh(gh, since, until, out, src):
    weights = {}
    for cwd, n in out["cwds"].items():
        repo = origin_repo(cwd)
        if repo:
            weights[repo] = weights.get(repo, 0) + n
    day = since.date().isoformat()
    for repo in sorted(weights, key=lambda r: (-weights[r], r))[:GH_REPOS]:
        src.files += 1
        view = gh_json(gh, ["repo", "view", repo, "--json", "visibility,defaultBranchRef"]) or {}
        public = str(view.get("visibility", "")).upper() == "PUBLIC"
        prov = "public" if public else "synthetic"
        branch = (view.get("defaultBranchRef") or {}).get("name") or "main"
        prs = gh_json(gh, ["pr", "list", "-R", repo, "--state", "merged", "--search", f"merged:>={day}", "--limit",
                           "200", "--json", "number,title,body,mergedAt,url"]) or []
        src.records += len(prs)
        prs = [p for p in prs if since <= (parse_time(p.get("mergedAt") or "") or until) < until]
        numbers = {p.get("number") for p in prs}
        for pr in prs:
            merged = parse_time(pr["mergedAt"])
            title, where = pr.get("title") or "", pr.get("url") or f"{repo}#{pr.get('number')}"
            if re.search(r"\brevert", title, re.I):
                out["items"].append(item("revert", where, title, merged, prov, repo))
            fixed = {int(n) for clause in FIX_CLAUSE.findall(f"{title}\n{pr.get('body') or ''}")
                     for other, n in FIX_REF.findall(clause) if not other or other.lower() == repo.lower()}
            fixed = sorted(n for n in fixed & numbers if n != pr.get("number"))  # a PR of this repo in the window
            if fixed:
                out["items"].append(item("fix-pr", where, f"{title} (fixes {', '.join(f'#{n}' for n in fixed)})",
                                         merged, prov, repo))
        runs = gh_json(gh, ["run", "list", "-R", repo, "--branch", branch, "--status", "failure", "--created",
                            f">={day}", "--limit", "100", "--json", "displayTitle,createdAt,url,workflowName"]) or []
        for r in runs:
            src.records += 1
            created = parse_time(r.get("createdAt") or "")
            if created and since <= created < until:
                out["items"].append(item("ci-fail-main", r.get("url") or repo,
                                         f"{r.get('workflowName')}: {r.get('displayTitle')}", created, prov, repo))


# ---------------------------------------------------------------- all sources


def observe(paths, since, until, gh="gh"):
    """{window, sources, items, counts, tally, codex_sessions} in [since, until). paths: projects, t3_db, codex,
    ledgers, hiden (None turns t3 or gh off)."""
    out = {"items": [], "cwds": {}, "refs": {}, "tally": {"owner": 0, "unknown": 0, "synthetic": 0},
           "t3_sessions": set(), "codex_sessions": {}}
    sources = {}
    steps = [("transcripts", lambda s: observe_transcripts(Path(paths["projects"]), since, until, out, s)),
             ("t3", paths.get("t3_db") and (lambda s: observe_t3(paths["t3_db"], since, until, out, s))),
             ("codex", lambda s: observe_codex(paths["codex"], since, until, out, s)),
             ("ledgers", lambda s: observe_ledgers(paths["ledgers"], since, until, out, s)),
             ("gh", gh and (lambda s: observe_gh(gh, since, until, out, s)))]
    for name, step in steps:
        src = Source(name)
        if not step:
            src.status = "off"
        else:
            try:
                step(src)
            except (OSError, ValueError, KeyError, RuntimeError, sqlite3.Error, subprocess.SubprocessError) as e:
                src.status, src.error = "fail", str(e)
        sources[name] = src.summary()
    if sources["transcripts"]["status"] == "ok":
        out["items"] += reference_items(paths["hiden"], out["refs"], until)
    unresolved = len(out["t3_sessions"]) if sources["t3"]["status"] != "ok" else 0
    out["tally"]["unknown"] += unresolved  # T3 sessions whose owner turns could not be read from the database
    seen, items = set(), []
    for it in out["items"]:
        if it["id"] not in seen:
            seen.add(it["id"])
            items.append(it)
    counts = {s: sum(1 for it in items if it["signal"] == s) for s in SIGNALS}
    return {"window": {"since": iso(since), "until": iso(until)}, "sources": sources, "items": items,
            "counts": counts, "tally": out["tally"], "codex_sessions": out["codex_sessions"]}


def default_paths(home):
    return {"projects": home / ".claude/projects", "t3_db": home / ".t3" / "userdata" / "statev2.sqlite",
            "codex": home / ".codex/sessions", "ledgers": home / ".claude/review-ledgers",
            "hiden": home / ".claude/skills/hiden"}
