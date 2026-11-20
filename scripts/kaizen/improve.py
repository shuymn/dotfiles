"""The weekly stage of the kaizen cycle (docs/kaizen.md §6 steps 5-8). Stdlib only; cycle.py calls weekly() in-process
after readiness and before publishing, and clear() for `cycle.py clear <attempt>`.

Nothing (no gh, model or file write) happens unless K/improve-enabled is a regular file. Then, holding K/.improve.lock:
  1. recover the newest attempt if it is still started or publishing;
  2. gate: no uncleared failed:remote-unknown, the newest attempt started 7 days ago or more, no open kaizen/ PR;
  3. lane: without a public GitHub PR or run among the items, write proposal.md and call no model; otherwise
     preflight, then `claude -p` edits a temp tree of the mirror at main, and the change is committed in the mirror,
     signed with the owner's SSH key, checked (one commit, apply.assess, prose caps, public-check, Codex) and pushed to
     a new branch with a PR. Every child runs through apply.bounded within the stage deadline.
An attempt is K/proposals/<YYYYMMDD>-<id>/ with result.json; remote refs are never deleted.
"""
import sys

sys.dont_write_bytecode = True

import difflib
import fcntl
import hashlib
import importlib.util
import io
import json
import math
import os
import posixpath
import re
import shlex
import shutil
import stat
import tarfile
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _sibling(name):
    spec = importlib.util.spec_from_file_location(f"kaizen_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


apply = _sibling("apply")
ready = apply.ready

STATE = ".local/state/kaizen-improve"
ENABLE, LOCK, PROPOSALS = "improve-enabled", ".improve.lock", "proposals"
WEEK = timedelta(days=7)
STAGE_SECONDS = 3600  # the stage's own deadline when the run has no explicit --deadline
DIGEST_RESERVE = 120  # left after the stage for the digest publish
SECONDS = {"claude": 2400, "codex": 1200, "gh": 60, "git": 120, "push": 120, "check": 120, "keygen": 30}
PUSH_MARGIN = 30  # no remote write starts with less time left than this
MODEL, EFFORT, MAX_BUDGET_USD = "claude-opus-5-5", "xhigh", "50"
TOOLS = "Read,Edit,Write,Grep,Glob"
CLAUDE_ENV = ("PATH", "HOME", "USER", "LANG", "TMPDIR")
HOOK = "home/dot_claude/hooks/executable_attention-budget.py"
WRITING = "scripts/kaizen/writing.md"
PUBLIC_CHECK = HERE / "public-check"
PUBLIC_WHERE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/(?:pull|actions/runs)/\d+")
ATTEMPT = re.compile(r"\d{8}-[0-9a-f]{6}")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
CODE_SPAN = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)", re.S)
INLINE_LINK = re.compile(r"\]\(\s*(<[^>\n]*>|[^)\s]+)")
REFERENCE = re.compile(r"^ {0,3}\[[^\]\n]+\]:[ \t]*(<[^>\n]*>|\S+)", re.M)
UNFINISHED = ("started", "publishing")
REMOTE_UNKNOWN = "failed:remote-unknown"
TASK = """\
## Task

The working directory is a copy of the public dotfiles repository at commit {base}. Its agent instructions live in
home/dot_claude/skills/** and home/dot_claude/agents/**.

Using only the evidence above, make at most one change to those instructions. Prefer, in this order: a mechanism,
delivery at an event, deleting text, adding text. Edit only existing files under home/dot_claude/skills/ and
home/dot_claude/agents/; create, delete or rename nothing. If the evidence does not justify a change, return
change: false.

Return evidence_ids (the ids above the change rests on), summary, watch (the signal to observe after the merge),
commit_message (Conventional Commits, English), pr_title and pr_body. Everything you return may be published: write
nothing that the evidence and the repository do not already show.
"""
SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["change", "evidence_ids", "summary", "watch", "commit_message", "pr_title", "pr_body"],
          "properties": {"change": {"type": "boolean"}, "evidence_ids": {"type": "array", "items": {"type": "string"}},
                         **{k: {"type": "string"} for k in ("summary", "watch", "commit_message", "pr_title",
                                                             "pr_body")}}}
VERDICT = {"type": "object", "additionalProperties": False, "required": ["high"],
           "properties": {"high": {"type": "array", "items": {"type": "string"}}}}
REVIEW = """\
Review this proposed change to an agent's instructions before it is published as a pull request. Report as HIGH only
problems that should block it: judgment the instructions lose, a guard that is loosened, case-specific nouns that read
as a general rule, or a relative link that no longer resolves. Return {{"high": []}} when there are none.

## Evidence brief
{brief}
## Commit message
{message}
## PR title
{title}
## PR body
{body}
## Diff
{diff}"""


class Stop(Exception):
    """The attempt ends with this outcome."""

    def __init__(self, outcome, detail=None):
        super().__init__(outcome)
        self.outcome, self.detail = outcome, detail


class Skip(Exception):
    """The stage ends before an attempt (retried at the next run)."""


class Deadline(Exception):
    """The stage deadline passed."""


def utc(now):
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def matches(value, schema):
    """value against the two flat schemas above (object of required keys, strings, booleans, arrays of strings)."""
    t = schema["type"]
    if t == "object":
        return (isinstance(value, dict) and set(value) == set(schema["required"])
                and all(matches(value[k], schema["properties"][k]) for k in value))
    if t == "array":
        return isinstance(value, list) and all(matches(v, schema["items"]) for v in value)
    return isinstance(value, {"string": str, "boolean": bool}[t])


def finite_cost(value):
    """value when it is a finite number (not a bool), else None; an int too large for a float is not finite."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return value if math.isfinite(value) else None
    except OverflowError:
        return None


def markdown_links(text):
    """The destinations of inline links and reference definitions, outside fenced and inline code, with an <...>
    destination unwrapped."""
    kept, fence = [], None
    for line in text.splitlines():
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)[0] * len(m.group(1))
        elif fence is not None and m and m.group(1).startswith(fence):
            fence = None
        elif fence is None:
            kept.append(line)
    prose = CODE_SPAN.sub("", "\n".join(kept))
    found = INLINE_LINK.findall(prose) + REFERENCE.findall(prose)
    return {t[1:-1] if t.startswith("<") and t.endswith(">") else t for t in found}


def blob_id(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def enabled(k):
    try:
        return stat.S_ISREG(os.lstat(k / ENABLE).st_mode)
    except OSError:
        return False


def take_lock(k, block=False):
    k.mkdir(parents=True, exist_ok=True)
    f = open(k / LOCK, "a")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | (0 if block else fcntl.LOCK_NB))
    except BlockingIOError:
        f.close()
        return None
    return f


def regular(path):
    try:
        return stat.S_ISREG(os.stat(path).st_mode) and os.access(path, os.R_OK)
    except OSError:
        return False


# ---------------------------------------------------------------- attempts

class Attempt:
    def __init__(self, path):
        self.dir = Path(path)
        self.data = json.loads((self.dir / "result.json").read_text())

    @classmethod
    def create(cls, k, now, fields):
        """K/proposals/<YYYYMMDD>-<id>/ with result.json, made by mkdtemp and rename so it appears complete."""
        proposals = k / PROPOSALS
        proposals.mkdir(parents=True, exist_ok=True)
        day = now.astimezone(timezone.utc).strftime("%Y%m%d")
        tmp = Path(tempfile.mkdtemp(dir=proposals, prefix=".new-"))
        try:
            while True:
                name = f"{day}-{os.urandom(3).hex()}"
                if not os.path.lexists(proposals / name):
                    break
            data = {"id": name, "started": utc(now), "outcome": "started", **fields}
            save(tmp / "result.json", data)
            os.rename(tmp, proposals / name)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return cls(proposals / name)

    def update(self, **fields):
        self.data.update(fields)
        save(self.dir / "result.json", self.data)

    def remote(self, **fields):
        self.update(remote={**(self.data.get("remote") or {}), **fields})

    def write(self, name, data):
        (self.dir / name).write_bytes(data if isinstance(data, bytes) else data.encode())


def save(path, value):
    """Atomic and durable: temp file, fsync, rename, fsync of the directory."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, indent=1, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise
    dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def newest(k):
    """The newest attempt (by its start, then its name), or None. An attempt whose result.json is unreadable is
    returned as one that blocks the gate."""
    found = []
    try:
        entries = list((k / PROPOSALS).iterdir())
    except FileNotFoundError:
        return None
    for entry in entries:
        if not ATTEMPT.fullmatch(entry.name) or not stat.S_ISDIR(entry.lstat().st_mode):
            continue
        try:
            a = Attempt(entry)
            key = str(a.data["started"])
        except (OSError, ValueError, KeyError, TypeError) as e:
            a = None
            key = "~"  # sorts after every timestamp: an unreadable attempt is treated as the newest
            found.append((key, entry.name, entry, str(e)))
            continue
        found.append((key, entry.name, a, None))
    if not found:
        return None
    _, _, a, error = max(found, key=lambda f: (f[0], f[1]))
    if error:
        raise Skip(f"unreadable attempt {a}: {error}")
    return a


def remove_tree(state, path):
    """Remove a tree this stage made: a tree-* directory directly under the state dir, never through a symlink."""
    if not path:
        return
    p = Path(path)
    if p.parent != state or not p.name.startswith("tree-"):
        return
    try:
        if stat.S_ISDIR(os.lstat(p).st_mode):
            shutil.rmtree(p)
    except FileNotFoundError:
        pass


def clear(k, attempt):
    """cycle.py clear <attempt>: lift the failed:remote-unknown stop of that attempt, under the stage's lock."""
    if not ATTEMPT.fullmatch(attempt or ""):
        raise SystemExit(f"kaizen: clear: {attempt!r} is not an attempt id")
    lock = take_lock(k)
    if lock is None:
        raise SystemExit("kaizen: clear: the weekly stage is running (K/.improve.lock is held)")
    try:
        try:
            a = Attempt(k / PROPOSALS / attempt)
        except (OSError, ValueError) as e:
            raise SystemExit(f"kaizen: clear: {attempt}: {e}") from e
        if a.data.get("outcome") != REMOTE_UNKNOWN:
            raise SystemExit(f"kaizen: clear: {attempt} is {a.data.get('outcome')}, not {REMOTE_UNKNOWN}")
        a.update(cleared=True)
        return {"cleared": attempt, "branch": (a.data.get("remote") or {}).get("branch")}
    finally:
        lock.close()


# ---------------------------------------------------------------- the stage

def weekly(k, home, repo, slug, items, ready_results, now, deadline, gh="gh", sources=None):
    """record["improver"]: {enabled, status, attempt (the newest, summarized), cost_usd (this run's Claude cost: 0,
    a number or "unknown"), codex_runs, decisions}. sources are observe's, whose gh status says whether the absence of
    public items can be trusted."""
    res = {"enabled": enabled(k), "status": "off", "attempt": None, "cost_usd": 0, "codex_runs": 0, "decisions": []}
    if not res["enabled"]:
        return res
    lock = take_lock(k)
    if lock is None:
        res["status"] = "skipped:locked"
    else:
        try:
            Stage(k, Path(home), repo, slug, gh, deadline, res).run(items, ready_results, now, sources or {})
        except Skip as e:
            res["status"] = f"skipped:{e}"
        finally:
            lock.close()
    try:
        a = newest(k)
    except Skip as e:
        res["decisions"].append(f"improver: {e}")
        a = None
    if a:
        res["attempt"] = summary(a)
        res["decisions"] += attempt_decisions(a)
    return res


def summary(a):
    d = a.data
    outcome = str(d.get("outcome"))
    return {"id": d.get("id"), "dir": str(a.dir), "started": d.get("started"), "outcome": outcome,
            "cost_usd": d.get("cost_usd", "unknown"), "pr": outcome[3:] if outcome.startswith("pr ") else None,
            "watch": d.get("watch"), "cleared": d.get("cleared", False),
            "branch": (d.get("remote") or {}).get("branch"), "reason": d.get("reason")}


def attempt_decisions(a):
    d, s = a.data, summary(a)
    if s["outcome"] == REMOTE_UNKNOWN and not s["cleared"]:
        return [f"improver: branch {s['branch']} is in an unknown remote state ({d.get('reason')}); check its PR, "
                f"then cycle.py clear {s['id']} (the weekly stage stays stopped until then)"]
    if s["outcome"] == "publishing":
        return [f"improver: branch {s['branch']} is publishing ({d.get('reason') or 'no PR confirmed yet'}); the next "
                "run looks for its PR"]
    if s["outcome"].startswith(("proposal:", "failed:")) and s["outcome"] != REMOTE_UNKNOWN:
        return [f"improver: {s['outcome']}" + (f" ({d['reason']})" if d.get("reason") else "") + f" — {a.dir}"]
    return []


class Stage:
    def __init__(self, k, home, repo, slug, gh, deadline, res):
        self.k, self.home, self.repo, self.slug, self.gh = k, home, repo, slug, gh
        self.deadline, self.res = deadline, res
        self.state = home / STATE
        self.mirror = self.state / "mirror.git"
        self.genv = {**apply.git_env(self.state), "GIT_NO_REPLACE_OBJECTS": "1"}
        self._files = None

    # -- children
    def call(self, argv, env, seconds, cwd=None, input=None):
        """apply.bounded; Deadline when the stage deadline was what stopped it."""
        try:
            return apply.bounded(argv, env, self.deadline, seconds, cwd=cwd, input=input)
        except apply.Timeout as e:
            if e.at_deadline:
                raise Deadline(str(e)) from e
            raise

    def git(self, *args, input=None, env=None, git_dir=True):
        argv = ["git", *(["--git-dir", str(self.mirror)] if git_dir else []), *args]
        code, out, err = self.call(argv, env or self.genv, SECONDS["git"], input=input)
        if code != 0:
            raise apply.ApplyError(f"git {' '.join(args[:3])}: exit {code}: {err.decode(errors='replace')[-300:]}")
        return out

    def gh_run(self, argv, seconds=None):
        code, out, err = self.call(argv, dict(os.environ), seconds or SECONDS["gh"])
        return code, out.decode(errors="replace"), err.decode(errors="replace").strip()[-300:]

    # -- the order of D1
    def run(self, items, ready_results, now, sources):
        a = newest(self.k)
        if a and a.data.get("outcome") in UNFINISHED:
            try:
                self.recover(a)
            except Deadline:
                self.res["status"] = "skipped:deadline in recovery"
                return
        if a and a.data.get("outcome") == REMOTE_UNKNOWN and not a.data.get("cleared"):
            raise Skip("remote-unknown")
        if a and now - (datetime.fromisoformat(str(a.data["started"]).replace("Z", "+00:00"))) < WEEK:
            raise Skip("not due")
        if not self.slug:
            raise Skip("no GitHub origin")
        try:
            open_prs = ready.open_kaizen_prs(self.slug, self.gh, runner=self.gh_run)
        except (ValueError, KeyError, TypeError, AttributeError, apply.ApplyError) as e:
            raise Skip(f"gh: {e}") from e
        except Deadline as e:
            raise Skip("deadline") from e
        if open_prs:
            raise Skip(f"open kaizen PR #{open_prs[0].get('number')}")
        public = [it for it in items
                  if it.get("provenance") == "public" and PUBLIC_WHERE.fullmatch(str(it.get("where")))]
        if not public:
            observed = (sources.get("gh") or {}).get("status")
            if observed != "ok":  # an unread source is not evidence of no public items; retry the next day
                raise Skip(f"GitHub observation {observed or 'missing'}")
            self.no_public_evidence(items, ready_results, now)
        else:
            self.model_lane(public, now)

    def no_public_evidence(self, items, ready_results, now):
        a = Attempt.create(self.k, now, {"lane": "proposal", "cost_usd": 0})
        r3 = (ready_results.get("R3") or {})
        lines = ["# 提案（公開の証拠が無い週。モデルは呼んでいない）", "", "## 候補"]
        lines += ([f"- {it.get('id')} {it.get('signal')} {it.get('where')} — {it.get('excerpt')}" for it in items]
                  or ["- なし"])
        lines += ["", "## R3", f"- {r3.get('status')}: {r3.get('detail')}", ""]
        a.write("proposal.md", "\n".join(lines))
        a.update(outcome="proposal:no-public-evidence")
        self.res["status"] = "proposal"

    # -- preflight (D2): failures skip without an attempt
    def preflight(self):
        if not self.repo or not regular(Path(self.repo) / "host.toml"):
            raise Skip("host.toml unreadable")
        if os.path.lexists(self.k / "private-terms") and not regular(self.k / "private-terms"):
            raise Skip("private-terms unreadable")  # present but broken: fail closed; absent means no terms
        ident = self.identity()
        code, _, err = self.call(["ssh-keygen", "-y", "-P", "", "-f", ident["key"]], self.minimal_env(),
                                 SECONDS["keygen"])
        if code != 0:
            raise Skip("signing key unusable")
        code, _, err = self.call(["claude", "auth", "status"], self.minimal_env(), SECONDS["gh"])
        if code != 0:
            raise Skip("claude auth status failed")
        return ident

    def minimal_env(self):
        env = {k: os.environ[k] for k in CLAUDE_ENV if k in os.environ}
        env["HOME"] = str(self.home)
        return env

    def identity(self):
        """user.name, user.email and the private key path from ~/.config/git/config.local, read by this process
        only."""
        config = self.home / ".config/git/config.local"
        values = {}
        for key in ("user.name", "user.email", "user.signingkey"):
            try:
                values[key] = self.git("config", "--file", str(config), "--get", key, git_dir=False).decode().strip()
            except apply.ApplyError as e:
                raise Skip(f"no {key} in the local git config") from e
        key = values["user.signingkey"]
        key = str(self.home) + key[1:] if key.startswith("~/") else key
        key = key[:-4] if key.endswith(".pub") else key
        if not regular(key):
            raise Skip("signing key unreadable")
        return {"name": values["user.name"], "email": values["user.email"], "key": key}

    # -- the model lane
    def model_lane(self, public, now):
        try:
            ident = self.preflight()
            url = apply.public_url(self.repo, env=self.genv, deadline=self.deadline)
            _, base = apply.sync_mirror(self.state, url, deadline=self.deadline)
            writing = self.git("show", f"{base}:{WRITING}").decode()
        except (apply.ApplyError, OSError, Deadline) as e:
            raise Skip(f"before the attempt: {e}") from e
        self.public = {it["id"]: it for it in public}
        brief = self.brief(public)
        a = Attempt.create(self.k, now, {"lane": "model", "base": base, "brief_ids": [it["id"] for it in public],
                                         "cost_usd": "unknown", "repo": self.slug})
        a.write("brief.md", brief)
        self.res["status"] = "attempted"
        tree = work = None
        try:
            tree = Path(tempfile.mkdtemp(dir=self.state, prefix="tree-"))
            a.update(tree=str(tree))
            work = Path(tempfile.mkdtemp(dir=self.state, prefix="work-"))
            self.attempt(a, ident, url, base, brief, writing, tree, work)
        except Stop as s:
            a.update(outcome=s.outcome, **({"reason": s.detail} if s.detail else {}))
        except Deadline as e:
            if not (a.data.get("remote") or {}).get("push_dispatched"):
                a.update(outcome="failed:timeout", reason=str(e))
            else:
                a.update(reason=f"deadline after the push was dispatched: {e}")
        except Exception as e:  # noqa: BLE001 — any other error ends the attempt, never the run
            if (a.data.get("remote") or {}).get("push_dispatched"):
                a.update(reason=f"{type(e).__name__}: {e}")  # stays publishing; the next run recovers it
            else:
                a.update(outcome="failed:error", reason=f"{type(e).__name__}: {e}")
        finally:
            remove_tree(self.state, tree)
            if work is not None and stat.S_ISDIR(os.lstat(work).st_mode):
                shutil.rmtree(work)
        self.res["cost_usd"] = a.data.get("cost_usd", "unknown")

    def brief(self, public):
        """The public brief: id, signal, URL and excerpt of public items, nothing else."""
        lines = ["## Evidence (public GitHub items of the last 7 days)", ""]
        lines += [f"- id {it['id']} | {it['signal']} | {it['where']} | {it['excerpt']}" for it in public]
        return "\n".join(lines) + "\n"

    def attempt(self, a, ident, url, base, brief, writing, tree, work):
        archive = self.git("archive", "--format=tar", base)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tree, filter="data")
        prompt = f"{brief}\n## Writing rules\n\n{writing}\n{TASK.format(base=base)}"
        try:
            out = self.claude(a, tree, prompt)
        finally:
            a.write("diff.patch", self.tree_diff(tree, base))  # what the model left, for the owner, whatever follows
        a.update(watch=out["watch"], summary=out["summary"], evidence_ids=out["evidence_ids"])
        if not out["change"]:
            raise Stop("no-change")
        if not out["evidence_ids"] or not set(out["evidence_ids"]) <= set(a.data["brief_ids"]):
            raise Stop("proposal:evidence-ids", f"cited {out['evidence_ids']}")
        changed = self.changed_set(tree, base)
        remove_tree(self.state, tree)
        title, message = out["pr_title"].strip(), out["commit_message"].strip()
        if not title or "\n" in title or not message:
            raise Stop("proposal:metadata", "blank or multi-line title, or blank commit message")
        urls = [self.public[i]["where"] for i in dict.fromkeys(out["evidence_ids"])]
        body = out["pr_body"].strip()
        if not body:
            raise Stop("proposal:metadata", "blank body")
        body = f"{body}\n\nEvidence:\n" + "".join(f"- {u}\n" for u in urls)
        a.write("title.txt", title)
        a.write("body.md", body)
        branch = f"kaizen/improve-{a.data['id']}"
        a.update(branch=branch, frozen={"title": hashlib.sha256(title.encode()).hexdigest(),
                                        "body": hashlib.sha256(body.encode()).hexdigest()})
        oid = self.commit(base, changed, message, ident, work)
        a.update(oid=oid)
        self.check(a, base, oid, changed, branch)
        self.codex(a, work, brief, message, title, body)
        self.publish(a, url, oid, branch)

    def claude(self, a, tree, prompt):
        argv = ["claude", "-p", "--safe-mode", "--restricted", "--strict-mcp-config", "--tools", TOOLS,
                "--permission-mode", "acceptEdits", "--permission-prompts", "none", "--no-session-persistence",
                "--output-format", "json", "--json-schema", json.dumps(SCHEMA), "--model", MODEL, "--effort", EFFORT,
                "--max-budget-usd", MAX_BUDGET_USD]
        try:
            code, out, err = self.call(argv, self.minimal_env(), SECONDS["claude"], cwd=str(tree),
                                       input=prompt.encode())
        except apply.Timeout as e:
            raise Stop("failed:timeout", str(e)) from e
        try:
            result = json.loads(out)
        except ValueError:
            result = None
        cost = finite_cost(result.get("total_cost_usd")) if isinstance(result, dict) else None
        if cost is not None:
            a.update(cost_usd=cost)
        if not (code == 0 and isinstance(result, dict) and result.get("subtype") == "success"
                and result.get("is_error") is False and matches(result.get("structured_output"), SCHEMA)):
            raise Stop("failed:model-result", f"exit {code}: {err.decode(errors='replace')[-200:]}")
        return result["structured_output"]

    def base_files(self, base):
        """{path: (mode, blob id)} of every blob at base, read once."""
        if self._files is None:
            self._files = {path: (mode, obj) for mode, kind, obj, path in
                           apply.parse_ls_tree(self.git("ls-tree", "-r", "-z", "--full-tree", base)) if kind == "blob"}
        return self._files

    def tree_diff(self, tree, base):
        """A unified diff of every regular file the tree adds, changes or lacks against base; other kinds of change
        are named. Text only: it is a record for the owner, not what is published."""
        want, out, seen = self.base_files(base), [], set()

        def old(path):
            return self.git("show", f"{base}:{path}").decode(errors="replace").splitlines(keepends=True)

        for top, dirs, files in os.walk(tree):
            for name in sorted(dirs + files):
                full = os.path.join(top, name)
                st = os.lstat(full)
                rel = os.path.relpath(full, tree)
                if stat.S_ISDIR(st.st_mode):
                    continue
                seen.add(rel)
                mode = want.get(rel, (None,))[0]
                before = (f"link to {''.join(old(rel))}" if mode == "120000" else f"mode {mode}") if mode else "absent"
                if stat.S_ISLNK(st.st_mode):
                    target = os.readlink(full)
                    if mode != "120000" or blob_id(os.fsencode(target)) != want[rel][1]:
                        out.append(f"# {rel}: {before} -> link to {target}\n")
                    continue
                if not stat.S_ISREG(st.st_mode):
                    out.append(f"# {rel}: {before} -> not a regular file\n")
                    continue
                now = "100755" if st.st_mode & 0o111 else "100644"
                if mode and mode != now:
                    out.append(f"# {rel}: {before} -> mode {now}\n")
                    if mode == "120000":
                        continue
                with open(full, "rb") as f:
                    data = f.read()
                if rel in want and blob_id(data) == want[rel][1]:
                    continue
                out += difflib.unified_diff(old(rel) if rel in want else [],
                                            data.decode(errors="replace").splitlines(keepends=True),
                                            f"a/{rel}" if rel in want else "/dev/null", f"b/{rel}")
        for rel in sorted(set(want) - seen):
            out += difflib.unified_diff(old(rel), [], f"a/{rel}", "/dev/null")
        return "".join(out)

    def changed_set(self, tree, base):
        """{path: new bytes}: modifications of 100644 blobs that are still regular non-executable files. Anything else
        (a new, deleted or retyped path, an edit to another mode) ends the attempt as a proposal."""
        want = self.base_files(base)
        changed, seen = {}, set()
        for top, dirs, files in os.walk(tree):
            for name in dirs + files:
                full = os.path.join(top, name)
                st = os.lstat(full)
                if stat.S_ISDIR(st.st_mode):
                    continue
                rel = os.path.relpath(full, tree)
                seen.add(rel)
                if rel not in want:
                    raise Stop("proposal:tree", f"new path {rel}")
                mode, obj = want[rel]
                if stat.S_ISLNK(st.st_mode):
                    if mode != "120000" or blob_id(os.fsencode(os.readlink(full))) != obj:
                        raise Stop("proposal:tree", f"symlink changed: {rel}")
                    continue
                executable = bool(st.st_mode & 0o111)
                if not stat.S_ISREG(st.st_mode) or mode not in ("100644", "100755") or executable != (mode == "100755"):
                    raise Stop("proposal:tree", f"type or mode changed: {rel}")
                with open(full, "rb") as f:
                    data = f.read()
                if blob_id(data) != obj:
                    if mode != "100644":
                        raise Stop("proposal:tree", f"not a 100644 file: {rel}")
                    changed[rel] = data
        gone = sorted(set(want) - seen)
        if gone:
            raise Stop("proposal:tree", f"deleted {gone[0]}")
        if not changed:
            raise Stop("proposal:tree", "change: true without a diff")
        return changed

    def broken_links(self, base, changed):
        """Relative Markdown links added by the change whose target is no path (file or directory) of the tree."""
        paths = set(self.base_files(base))
        paths |= {"/".join(p.split("/")[:i]) for p in paths for i in range(1, p.count("/") + 1)}
        broken = []
        for path, data in sorted(changed.items()):
            old = markdown_links(self.git("show", f"{base}:{path}").decode(errors="replace"))
            for target in sorted(markdown_links(data.decode(errors="replace")) - old):
                if re.match(r"[a-z][a-z0-9+.-]*:|#|/", target):  # a URL, an anchor or an absolute path
                    continue
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target.split("#")[0]))
                if resolved not in paths:
                    broken.append(f"{path}: {target}")
        return broken

    def commit(self, base, changed, message, ident, work):
        """The candidate commit in the mirror: a temp index from base plus the new blobs, signed by commit-tree -S
        with the key path given on the command line; git reads no owner config."""
        env = {**self.genv, "GIT_INDEX_FILE": str(work / "index")}
        self.git("read-tree", base, env=env)
        for path, data in sorted(changed.items()):
            blob = self.git("hash-object", "-w", "--stdin", input=data, env=env).decode().strip()
            self.git("update-index", "--cacheinfo", f"100644,{blob},{path}", env=env)
        tree = self.git("write-tree", env=env).decode().strip()
        (work / "message").write_text(message + "\n")
        return self.git("-c", "gpg.format=ssh", "-c", f"user.signingkey={ident['key']}", "-c",
                        f"user.name={ident['name']}", "-c", f"user.email={ident['email']}", "commit-tree", "-S",
                        "-p", base, "-F", str(work / "message"), tree, env=env).decode().strip()

    def check(self, a, base, oid, changed, branch):
        if self.git("rev-list", "--count", f"{base}..{oid}").decode().strip() != "1":
            raise Stop("proposal:check", "not one commit")
        reader = apply.GitReader(self.mirror, "git", self.genv, self.deadline)
        targets, reason = apply.assess(reader, base, oid)
        if reason:
            raise Stop("proposal:assess", reason)
        if {source for source, _ in targets} != set(changed):
            raise Stop("proposal:assess", "the applicable targets differ from the changed files")
        over = self.caps(base, {rel: changed[source] for source, rel in targets})
        if over:
            raise Stop("proposal:caps", over)
        broken = self.broken_links(base, changed)
        if broken:
            raise Stop("proposal:links", "; ".join(broken)[:300])
        rc, out = self.public_check(a, base, oid, branch)
        a.update(public_check=out)
        if rc != 0:
            raise Stop("proposal:public-check", out[-300:])

    def public_check(self, a, base, oid, branch):
        """public-check of the frozen inputs, run with the job's Python in the mirror, git's environment clean."""
        argv = [sys.executable, str(PUBLIC_CHECK), f"{base}..{oid}", "--title", (a.dir / "title.txt").read_text(),
                "--body-file", str(a.dir / "body.md"), "--branch", branch,
                "--host-toml", str(Path(self.repo) / "host.toml"), "--private-terms", self.terms_file()]
        code, out, err = self.call(argv, self.genv, SECONDS["check"], cwd=str(self.mirror))
        return code, (out + err).decode(errors="replace")

    def terms_file(self):
        """K/private-terms, or an empty file when the owner keeps none: the terms are optional."""
        terms = self.k / "private-terms"
        return str(terms) if os.path.lexists(terms) else os.devnull

    def caps(self, base, targets):
        """The attention hook's own rules, from its source at base, with the owner's live budget.json: a .md file in a
        capped dir needs a prose entry, and a file with an entry must fit its cap in UTF-8 bytes."""
        try:
            source = self.git("show", f"{base}:{HOOK}").decode()
            spec = importlib.util.spec_from_loader("kaizen_attention_budget", loader=None)
            hook = importlib.util.module_from_spec(spec)
            with home_env(self.home):
                exec(compile(source, HOOK, "exec"), hook.__dict__)
                budget = hook.load_budget((self.home / ".claude/attention/budget.json").read_text())
                _, prose = hook.tracked(budget)
                for rel, data in sorted(targets.items()):
                    path = hook.expand("~/" + rel)
                    if hook.in_capped_dir(path) and path not in prose:
                        return f"{rel} has no prose entry"
                    if path in prose and len(data) > prose[path]:
                        return f"{rel} is {len(data)} bytes; the cap is {prose[path]}"
        except Exception as e:  # noqa: BLE001 — a hook that cannot be used is a refusal, not a pass
            return f"attention hook unusable: {type(e).__name__}: {e}"
        return None

    def codex(self, a, work, brief, message, title, body):
        """Codex reviews the frozen candidate; its verdict can only block."""
        empty = work / "empty"
        empty.mkdir()
        (work / "verdict.schema.json").write_text(json.dumps(VERDICT))
        verdict = work / "verdict.json"
        argv = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only", "-c",
                "approval_policy=never", "-C", str(empty), "--output-schema", str(work / "verdict.schema.json"),
                "-o", str(verdict), "-"]
        prompt = REVIEW.format(brief=brief, message=message, title=title, body=body,
                               diff=(a.dir / "diff.patch").read_text())
        self.res["codex_runs"] += 1
        a.update(codex_runs=a.data.get("codex_runs", 0) + 1)
        try:
            code, _, err = self.call(argv, dict(os.environ), SECONDS["codex"], input=prompt.encode())
        except apply.Timeout as e:
            raise Stop("proposal:codex", f"timed out: {e}") from e
        if code != 0:
            raise Stop("proposal:codex", f"exit {code}: {err.decode(errors='replace')[-200:]}")
        try:
            v = json.loads(verdict.read_text())
        except (OSError, ValueError) as e:
            raise Stop("proposal:codex", f"no valid verdict: {e}") from e
        if not matches(v, VERDICT):
            raise Stop("proposal:codex", "invalid verdict")
        a.update(codex_high=v["high"])
        if v["high"]:
            raise Stop("proposal:codex-high", "; ".join(v["high"])[:300])

    def frozen(self, a):
        """True when title.txt and body.md still hold the bytes public-check checked."""
        f = a.data.get("frozen") or {}
        return all(hashlib.sha256((a.dir / name).read_bytes()).hexdigest() == f.get(key)
                   for name, key in (("title.txt", "title"), ("body.md", "body")))

    def publish(self, a, url, oid, branch):
        if self.deadline - time.monotonic() < PUSH_MARGIN:
            raise Stop("failed:timeout", "too little time left to publish")
        if not self.frozen(a):
            raise Stop("failed:frozen", "title or body changed after public-check")
        a.update(outcome="publishing")
        a.remote(repo=self.slug, ref=f"refs/heads/{branch}", branch=branch, oid=oid, push_dispatched=True)
        env = {**self.genv, "GH_CONFIG_DIR": os.environ.get("GH_CONFIG_DIR") or str(self.home / ".config/gh")}
        code, _, err = self.call(["git", "--git-dir", str(self.mirror), "-c", "credential.helper=", "-c",
                                  f"credential.helper=!{shlex.quote(self.gh)} auth git-credential", "push",
                                  f"--force-with-lease=refs/heads/{branch}:", url, f"{oid}:refs/heads/{branch}"],
                                 env, SECONDS["push"])
        if code != 0:
            a.update(reason=f"push: exit {code}: {err.decode(errors='replace')[-200:]}")
            return
        a.remote(pr_dispatched=True)
        remote = a.data["remote"]
        self.create(a, remote)
        try:
            prs = self.lookup(remote)
        except Stop as s:
            a.update(reason=s.detail)  # stays publishing; the next run looks again
            return
        if not self.adopt(a, prs, remote) and prs:
            raise Stop(REMOTE_UNKNOWN, f"{len(prs)} PR(s) for the branch; not exactly one matching repo, ref, oid "
                       "and base")

    def create(self, a, remote):
        """gh pr create in the recorded repo with the frozen title and body file. Its answer is not trusted: the
        attempt stays publishing until a lookup finds the one matching PR (--head names a ref, not a commit)."""
        if not self.frozen(a):
            raise Stop(REMOTE_UNKNOWN, "title or body changed after public-check; no PR was created")
        code, _, err = self.gh_run([self.gh, "pr", "create", "--repo", remote["repo"], "--base", "main", "--head",
                                    remote["branch"], "--title", (a.dir / "title.txt").read_text(), "--body-file",
                                    str(a.dir / "body.md")])
        if code != 0:
            a.update(reason=f"gh pr create: exit {code}: {err}")

    # -- recovery (D5 step 7)
    def recover(self, a):
        remove_tree(self.state, a.data.get("tree"))
        remote = a.data.get("remote") or {}
        if not remote.get("push_dispatched"):
            cost = finite_cost(a.data.get("cost_usd"))
            a.update(outcome="failed:interrupted", cost_usd="unknown" if cost is None else cost)
            return
        try:
            self.reconcile(a, remote)
        except Stop as s:
            a.update(outcome=s.outcome, reason=s.detail)
        except Deadline:
            raise
        except Exception as e:  # noqa: BLE001 — any other failure is a decision naming the branch, never a crash
            a.update(outcome=REMOTE_UNKNOWN, reason=f"recovery failed: {type(e).__name__}: {e}")

    def lookup(self, remote):
        owner = remote["repo"].split("/")[0]
        code, out, err = self.gh_run([self.gh, "api", "--paginate", "--slurp",
                                      f"repos/{remote['repo']}/pulls?state=all&head={owner}:{remote['branch']}"
                                      "&per_page=100"])
        try:
            if code != 0:
                raise ValueError(err)
            return ready.slurped(out)
        except ValueError as e:
            raise Stop(REMOTE_UNKNOWN, f"PR lookup failed: {e}") from e

    @staticmethod
    def adoptable(pr, remote):
        try:
            return (pr["head"]["repo"]["full_name"].lower() == remote["repo"].lower()
                    and pr["head"]["ref"] == remote["branch"] and pr["head"]["sha"] == remote["oid"]
                    and pr["base"]["ref"] == "main")
        except (KeyError, TypeError, AttributeError):
            return False

    def adopt(self, a, prs, remote):
        """Take the PR when it is the only one for the branch and matches repo, ref, oid and base."""
        if len(prs) == 1 and self.adoptable(prs[0], remote):
            a.update(outcome=f"pr {prs[0].get('html_url')}")
            return True
        return False

    def reconcile(self, a, remote):
        prs = self.lookup(remote)
        if self.adopt(a, prs, remote):
            return
        if prs:
            raise Stop(REMOTE_UNKNOWN, f"{len(prs)} PR(s) for the branch; not exactly one matching repo, ref, oid "
                       "and base")
        if remote.get("recovery_dispatched"):
            raise Stop(REMOTE_UNKNOWN, "no PR after the recovery create")
        url = f"https://github.com/{remote['repo']}.git"
        try:
            listed = self.git("-c", "credential.helper=", "ls-remote", url, remote["ref"], git_dir=False).decode()
        except apply.ApplyError as e:
            raise Stop(REMOTE_UNKNOWN, f"ls-remote failed: {e}") from e
        oids = [line.split()[0] for line in listed.splitlines() if line.strip()]
        if oids != [remote["oid"]]:
            raise Stop(REMOTE_UNKNOWN, "ref missing" if not oids else "the ref is at another commit")
        if not self.repo or not regular(Path(self.repo) / "host.toml"):
            raise Stop(REMOTE_UNKNOWN, "the checkout or its host.toml is unavailable, so the PR cannot be checked")
        rc, out = self.public_check(a, a.data["base"], remote["oid"], remote["branch"])
        if rc != 0:
            raise Stop(REMOTE_UNKNOWN, f"public-check now fails: {out[-200:]}")
        a.remote(recovery_dispatched=True)
        self.create(a, remote)
        if not self.adopt(a, self.lookup(remote), remote):
            raise Stop(REMOTE_UNKNOWN, "no matching PR after the recovery create")


@contextmanager
def home_env(home):
    """HOME set to the owner's home while the hook's ~ paths are expanded."""
    old = os.environ.get("HOME")
    os.environ["HOME"] = str(home)
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old
