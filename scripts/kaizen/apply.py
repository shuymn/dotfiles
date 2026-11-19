#!/usr/bin/env python3
"""Conditional automatic apply of the kaizen cycle (docs/kaizen.md §6 「マージの後」). Stdlib only; macOS only for
writes (renameatx_np). No chezmoi: v1 applies only modifications of plain files under home/dot_claude/skills/** and
home/dot_claude/agents/**, whose target is ~/.claude/<rest>, content the git blob, mode 0644.

  apply.py --check   fetch the mirror, then print the cursor, the journal and the pending merges; writes nothing but
                     the mirror. Only the next candidate is predicted (applied or where it stops); later ones are
                     compared with the live snapshot as it is now. Exit 0 when the next step would not stop, 1 when it
                     would, 2 on error (for humans only).
The cycle calls run() in-process (cycle.py run); the owner commands adopt and resolve are cycle.py commands. State lives in A = <home>/.local/state/kaizen-apply: .apply.lock,
applied.json (the cursor L), journal.json, backup/<run>/, mirror.git (a bare clone of main fetched from the public
HTTPS URL of the checkout's GitHub origin). The owner's checkout is read only for that URL.
"""
import sys

sys.dont_write_bytecode = True

import argparse
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from importlib import util as importlib_util
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _sibling(name):
    spec = importlib_util.spec_from_file_location(f"kaizen_{name}", HERE / f"{name}.py")
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ready = _sibling("ready")

STATE = ".local/state/kaizen-apply"
ROOTS = ("home/dot_claude/skills/", "home/dot_claude/agents/")
SOURCE_DIR, TARGET_DIR = "home/dot_claude/", ".claude/"
# Paths no chezmoi apply reads, so a merge may change them next to its v1 targets. scripts/kaizen/ reaches the
# daily job only through the owner's switch; other scripts/ feed the chezmoi config and are not listed.
REPO_ONLY = ("docs/", "tests/", ".github/", "scripts/kaizen/", "README.md", "AGENTS.md", "CLAUDE.md")
# chezmoi source attributes; a component starting with one (or with ".") is not a plain name
ATTRIBUTES = ("after_", "before_", "create_", "dot_", "empty_", "encrypted_", "exact_", "executable_", "external_",
              "literal_", "modify_", "once_", "onchange_", "private_", "readonly_", "remove_", "run_", "symlink_")
SUFFIXES = (".tmpl", ".age", ".asc", ".literal")
MODE = 0o644
BUDGET = 300  # seconds the apply stage may take; past them it stops between target steps and the next run goes on
TIMEOUTS = {"clone": 300, "fetch": 60, "read": 30}
STANDALONE_DEADLINE = 600
RENAME_SWAP = 0x2
CONTROL = re.compile(r"\{\{-?\s*(?:/\*.*?\*/|(?:if|else|else\s+if|end|range|with)\b[^{}]*?)\s*-?\}\}")
GITHUB = re.compile(r"^(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
                    r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
PR = re.compile(r"Merge pull request #(\d+)|\(#(\d+)\)\s*$")
# every spelling chezmoi reads as an ignore or remove file, in any source directory
RULE_FILES = (".chezmoiignore", ".chezmoiignore.tmpl", ".chezmoiremove", ".chezmoiremove.tmpl")
UNSUPPORTED = re.compile(r"[{}\[\]\\]")  # pattern syntax pattern_match does not implement: refuse instead
HEX40, HEX64 = re.compile(r"[0-9a-f]{40}"), re.compile(r"[0-9a-f]{64}")
STEPS = ("staged", "swapped", "clean", "unresolved")


class ApplyError(Exception):
    """An apply stage that cannot go on: reported in the result and as a decision."""


class WalkError(OSError):
    pass


class InvalidState(ApplyError):
    """applied.json or journal.json is not what apply writes."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- git: environment, mirror, reader

def git_env(state):
    """The environment of every git call, built from scratch so no GIT_* variable or config can redirect it."""
    env = {"PATH": os.environ.get("PATH") or os.defpath, "HOME": str(state), "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}
    if os.environ.get("LANG"):
        env["LANG"] = os.environ["LANG"]
    return env


def run_git(git, args, env, timeout, deadline):
    """stdout bytes. The timeout is bounded by the deadline (monotonic); subprocess.run kills git on a timeout or on
    any exception (a SystemExit from the cycle's signal handlers included) and waits for it."""
    left = min(timeout, deadline - time.monotonic())
    if left <= 0:
        raise ApplyError(f"git {args[0]}: no time left before the deadline")
    try:
        p = subprocess.run([git, *args], env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=left)
    except FileNotFoundError as e:
        raise ApplyError(f"git not found: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise ApplyError(f"git {' '.join(map(str, args[:4]))} timed out after {left:.0f}s") from e
    if p.returncode != 0:
        raise ApplyError(f"git {' '.join(map(str, args[:4]))}: exit {p.returncode}: "
                         f"{p.stderr.decode(errors='replace').strip()[-300:]}")
    return p.stdout


def public_url(repo, git="git", env=None, deadline=None):
    """The public HTTPS URL of the checkout's GitHub origin (ssh forms converted)."""
    if repo is None:
        raise ApplyError("no checkout to read the origin URL from (chezmoi source-path failed)")
    out = run_git(git, ["-C", str(repo), "remote", "get-url", "origin"], env or git_env(Path(repo)),
                  TIMEOUTS["read"], deadline or time.monotonic() + TIMEOUTS["read"])
    m = GITHUB.match(out.decode().strip())
    if not m:
        raise ApplyError(f"origin of {repo} is not a GitHub repository")
    return f"https://github.com/{m.group(1)}/{m.group(2)}.git"


def sync_mirror(state, url, git="git", deadline=None):
    """Clone A/mirror.git on first use (into a temp dir renamed into place), fetch main from url, and return
    (reader, head) with head pinned for the whole run."""
    deadline = deadline or time.monotonic() + STANDALONE_DEADLINE
    env, mirror = git_env(state), state / "mirror.git"
    state.mkdir(parents=True, exist_ok=True)
    try:
        st = os.lstat(mirror)
    except FileNotFoundError:
        st = None
    if st is None:
        tmp = tempfile.mkdtemp(dir=state, prefix=".mirror.")
        try:
            run_git(git, ["-c", "credential.helper=", "clone", "--bare", "--single-branch", "--branch", "main",
                          "--no-tags", url, os.path.join(tmp, "m")], env, TIMEOUTS["clone"], deadline)
            os.rename(os.path.join(tmp, "m"), mirror)
        finally:
            if stat.S_ISDIR(os.lstat(tmp).st_mode):  # our mkdtemp directory, never a symlink
                shutil.rmtree(tmp)
    elif not stat.S_ISDIR(st.st_mode):
        raise ApplyError(f"{mirror} is not a directory")
    base = ["--git-dir", str(mirror)]
    run_git(git, [*base, "-c", "credential.helper=", "fetch", "--no-tags", url, "+refs/heads/main:refs/heads/main"],
            env, TIMEOUTS["fetch"], deadline)
    reader = GitReader(mirror, git, env, deadline)
    return reader, reader.resolve("refs/heads/main")


def parse_name_status(out):
    """[(status, path)] from `git diff -z --no-renames --name-status`."""
    fields = out.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    return [(fields[i].decode(), fields[i + 1].decode("utf-8", "surrogateescape")) for i in range(0, len(fields), 2)]


def parse_ls_tree(out):
    """[(mode, type, object, path)] from `git ls-tree -z`."""
    rows = []
    for rec in out.split(b"\0"):
        if rec:
            meta, path = rec.split(b"\t", 1)
            mode, kind, obj = meta.decode().split()
            rows.append((mode, kind, obj, path.decode("utf-8", "surrogateescape")))
    return rows


class GitReader:
    """The only git access of the apply core: read-only commands on the mirror."""

    def __init__(self, mirror, git, env, deadline):
        self.base, self.git, self.env, self.deadline = ["--git-dir", str(mirror)], git, env, deadline
        self.cache = {}

    def _git(self, *args):
        return run_git(self.git, [*self.base, *args], self.env, TIMEOUTS["read"], self.deadline)

    def resolve(self, rev):
        return self._git("rev-parse", "--verify", "--end-of-options", f"{rev}^{{commit}}").decode().strip()

    def first_parents(self, head):
        """[(commit, first parent or None)], newest first."""
        rows = []
        for line in self._git("rev-list", "--first-parent", "--parents", head).decode().splitlines():
            parts = line.split()
            rows.append((parts[0], parts[1] if len(parts) > 1 else None))
        return rows

    def changes(self, parent, commit):
        return parse_name_status(self._git("diff", "-z", "--no-renames", "--no-ext-diff", "--no-textconv",
                                           "--name-status", parent, commit, "--"))

    def blob(self, commit, path):
        """(mode, bytes) of the blob at path, or None."""
        key = ("blob", commit, path)
        if key not in self.cache:
            rows = parse_ls_tree(self._git("ls-tree", "-z", "--full-tree", commit, "--", path))
            row = next((r for r in rows if r[3] == path and r[1] == "blob"), None)
            self.cache[key] = (row[0], self._git("cat-file", "blob", row[2])) if row else None
        return self.cache[key]

    def names(self, commit, directory):
        """Entry names of a tree directory ("" is the root)."""
        args = ["ls-tree", "-z", "--full-tree", commit] + (["--", directory + "/"] if directory else [])
        return [r[3].rsplit("/", 1)[-1] for r in parse_ls_tree(self._git(*args))]

    def files(self, commit, prefixes):
        """[(mode, path)] of every blob under the prefixes."""
        return [(r[0], r[3]) for r in parse_ls_tree(self._git("ls-tree", "-r", "-z", "--full-tree", commit, "--",
                                                              *[p.rstrip("/") for p in prefixes])) if r[1] == "blob"]

    def subject(self, commit):
        return self._git("log", "-1", "--format=%s", commit).decode().strip()


# ---------------------------------------------------------------- eligibility (K1, L3, N2) and candidates (N6)

def pattern_match(pattern, path):
    """Doublestar glob: "*" stays within a segment, "**" stands for any number of segments."""
    def seg(p, parts):
        if not p:
            return not parts
        if p[0] == "**":
            return any(seg(p[1:], parts[i:]) for i in range(len(parts) + 1))
        return bool(parts) and fnmatchcase(parts[0], p[0]) and seg(p[1:], parts[1:])
    return seg(pattern.strip("/").split("/"), path.split("/"))


def plain(component):
    return bool(component) and not component.startswith((".", *ATTRIBUTES)) and not component.endswith(SUFFIXES)


def plain_target(path):
    """The target (relative to home) of a v1 source path, or None when the path is outside v1."""
    if not path.startswith(ROOTS):
        return None
    rest = path[len(SOURCE_DIR):]
    return TARGET_DIR + rest if all(plain(c) for c in rest.split("/")) else None


def target_name(name):
    """The target name chezmoi gives a source entry name (an over-approximation is fine: it only finds collisions)."""
    for suffix in SUFFIXES:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    while True:
        attr = next((a for a in ATTRIBUTES if name.startswith(a)), None)
        if attr is None:
            return name
        if attr == "literal_":
            return name[len(attr):]
        if attr == "dot_":
            return "." + name[len(attr):]
        name = name[len(attr):]


def rule_patterns(text):
    """(patterns, None) of an ignore or remove file, every pattern line regardless of conditionals; or (None, reason)
    for a template action that could emit a pattern (looked for before comments are cut, since an action after "#"
    can emit a line) or a pattern using syntax pattern_match does not implement."""
    patterns = []
    for line in text.splitlines():
        if "{{" in line:
            if CONTROL.fullmatch(line.strip()):
                continue
            return None, f"template line {line.strip()!r}"
        s = line.split("#", 1)[0].strip()
        if not s:
            continue
        if UNSUPPORTED.search(s):
            return None, f"unsupported pattern syntax {s!r}"
        patterns.append(s.lstrip("!").strip())
    return patterns, None


def ancestors(rel):
    parts = rel.split("/")
    return ["/".join(parts[:i]) for i in range(len(parts), 0, -1)]


def guards(reader, commit, targets):
    """The mapping guards at commit; a reason when one fails, else None."""
    root = reader.blob(commit, ".chezmoiroot")
    if root is None or root[1].strip() != b"home":
        return ".chezmoiroot is not home"
    config = reader.blob(commit, ".chezmoi.toml.tmpl")
    if config and b"umask" in config[1]:
        return ".chezmoi.toml.tmpl sets umask"
    for rules in RULE_FILES:
        b = reader.blob(commit, f"home/{rules}")
        if b is None:
            continue
        patterns, bad = rule_patterns(b[1].decode("utf-8", "replace"))
        if bad:
            return f"home/{rules}: {bad}"
        for _, rel in targets:
            for path in ancestors(rel):
                hit = next((p for p in patterns if pattern_match(p, path)), None)
                if hit:
                    return f"home/{rules} line {hit!r} matches {path}"
    for source, _ in targets:
        parts = source.split("/")
        for depth in range(1, len(parts)):
            directory, own = "/".join(parts[:depth]), parts[depth]
            names = reader.names(commit, directory)
            if depth > 1 and any(n in RULE_FILES for n in names):
                return f"{directory} has its own ignore or remove file"
            if any(n.startswith(".chezmoiexternal") for n in names):
                return f"{directory} has a .chezmoiexternal file"
            other = [n for n in names if n != own and target_name(n) == target_name(own)]
            if other:
                return f"{directory}/{own} collides with {', '.join(other)}"
    return None


def assess(reader, parent, commit):
    """(targets, None) when commit is applicable in v1, targets = [(source, target rel)]; else (None, reason)."""
    targets = []
    for status, path in reader.changes(parent, commit):
        if any(path == p or (p.endswith("/") and path.startswith(p)) for p in REPO_ONLY):
            continue
        if status != "M":
            return None, f"{ {'A': 'added', 'D': 'deleted', 'T': 'type change'}.get(status, status)} {path}"
        rel = plain_target(path)
        if rel is None:
            return None, f"outside v1: {path}"
        for c in (parent, commit):
            b = reader.blob(c, path)
            if b is None or b[0] != "100644":
                return None, f"not a 100644 blob at {c[:8]}: {path}"
            if not b[1].strip():
                return None, f"empty at {c[:8]}: {path}"
        targets.append((path, rel))
    if not targets:
        return None, "no change"
    reason = guards(reader, commit, targets)
    return (None, reason) if reason else (targets, None)


def managed_patterns(reader, commit):
    b = reader.blob(commit, ".claude/kaizen-managed")
    if b is None:
        return []
    return [l.strip() for l in b[1].decode("utf-8", "replace").splitlines() if l.strip() and not l.lstrip().startswith("#")]


def is_candidate(reader, parent, commit):
    """A first-parent commit is a candidate when it changes a home/ path of the managed list (of either side)."""
    if parent is None:
        return False
    pats = set(managed_patterns(reader, commit)) | set(managed_patterns(reader, parent)) or {"home/**"}
    return any(p.startswith("home/") and any(ready.pattern_match(m, p) for m in pats)
               for _, p in reader.changes(parent, commit))


def pr_of(subject):
    m = PR.search(subject or "")
    return f"#{m.group(1) or m.group(2)}" if m else None


# ---------------------------------------------------------------- filesystem: walk, look, classify, swap

def walk(root, parts):
    """An fd of root/parts..., every component opened with O_NOFOLLOW (root itself may be reached by a symlink)."""
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for p in parts:
            try:
                nfd = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except OSError as e:
                kind = "missing" if e.errno == errno.ENOENT else "symlinked or not a directory"
                raise WalkError(e.errno, f"{kind}: {p}") from e
            os.close(fd)
            fd = nfd
    except BaseException:
        os.close(fd)
        raise
    return fd


def ident(fd):
    st = os.fstat(fd)
    return [st.st_dev, st.st_ino]


def look(dir_fd, name):
    """What the entry name is: {"type": missing|symlink|other} or {"type": file, mode, bytes, ino}."""
    try:
        st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except FileNotFoundError:
        return {"type": "missing"}
    if not stat.S_ISREG(st.st_mode):
        return {"type": "symlink" if stat.S_ISLNK(st.st_mode) else "other"}
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    except OSError as e:
        return {"type": "other", "error": str(e)}
    with open(fd, "rb") as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode):
            return {"type": "other"}
        return {"type": "file", "mode": stat.S_IMODE(st.st_mode), "bytes": f.read(), "ino": [st.st_dev, st.st_ino]}


def snapshot(home, rel):
    """(live, parent identity) of a target; live is {"type": "parent", "detail"} when the walk fails."""
    parts = rel.split("/")
    try:
        fd = walk(home, parts[:-1])
    except WalkError as e:
        return {"type": "parent", "detail": e.strerror}, None
    try:
        return look(fd, parts[-1]), ident(fd)
    finally:
        os.close(fd)


def kind(live, old, new):
    """K2: done when live is the new blob, write when it is the old one, else conflict."""
    if live.get("type") == "file" and live.get("mode") == MODE:
        if live["bytes"] == new:
            return "done"
        if live["bytes"] == old:
            return "write"
    return "conflict"


def describe(live):
    t = live.get("type")
    if t == "file":
        return "edited" if live.get("mode") == MODE else f"mode {live['mode']:04o}"
    return live.get("detail") or t


_renameatx = None


def exchange(from_dir, from_name, to_dir, to_name):
    """renameatx_np(RENAME_SWAP): the two entries trade places in one step."""
    global _renameatx
    if _renameatx is None:
        try:
            f = ctypes.CDLL(None, use_errno=True).renameatx_np
        except AttributeError as e:
            raise OSError(errno.ENOSYS, "renameatx_np is unavailable") from e
        f.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        f.restype = ctypes.c_int
        _renameatx = f
    if _renameatx(from_dir, os.fsencode(from_name), to_dir, os.fsencode(to_name), RENAME_SWAP) != 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e), to_name)


def stage_backup(dir_fd, name, data):
    """Write B at the backup name (O_EXCL), mode 0644, fsynced; returns its (dev, ino)."""
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, MODE, dir_fd=dir_fd)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fchmod(fd, MODE)
        os.fsync(fd)
        return ident(fd)
    finally:
        os.close(fd)


# ---------------------------------------------------------------- state: cursor, journal, lock

class State:
    def __init__(self, home):
        self.home = Path(home)
        self.dir = self.home / STATE

    def read(self, name, default):
        try:
            return json.loads((self.dir / name).read_text())
        except FileNotFoundError:
            return default
        except (OSError, ValueError) as e:
            raise InvalidState(f"{self.dir / name} is unreadable: {e}") from e

    def applied(self):
        value = self.read("applied.json", None)
        if value is not None and not (isinstance(value, dict) and isinstance(value.get("commit"), str)
                                      and HEX40.fullmatch(value["commit"]) and isinstance(value.get("at"), str)
                                      and value.get("by") in ("cycle", "observed", "owner")):
            raise InvalidState(f"{self.dir / 'applied.json'} is not a cursor: {json.dumps(value)[:200]}")
        return value

    def journal(self):
        value = self.read("journal.json", {"entries": []})
        entries = value.get("entries") if isinstance(value, dict) else None
        if not isinstance(entries, list) or not all(valid_entry(e) for e in entries):
            raise InvalidState(f"{self.dir / 'journal.json'} is not a journal: {json.dumps(value)[:200]}")
        return entries

    def write(self, name, value):
        """Atomic and durable: temp file, fsync, rename, fsync of the directory; the temp file goes on failure."""
        self.dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=f".{name}.")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(value, f, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.dir / name)
        except BaseException:
            os.unlink(tmp)
            raise
        dfd = os.open(self.dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

    def save_journal(self, entries):
        self.write("journal.json", {"entries": entries})

    def lock(self):
        """The open .apply.lock with LOCK_EX held, or None when another apply, adopt or resolve holds it."""
        self.dir.mkdir(parents=True, exist_ok=True)
        f = open(self.dir / ".apply.lock", "a")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            f.close()
            return None
        return f


def relative(path):
    parts = path.split("/") if isinstance(path, str) else [""]
    return not path.startswith("/") and all(p not in ("", ".", "..") for p in parts)


def valid_entry(e):
    return (isinstance(e, dict) and isinstance(e.get("merge"), str) and bool(HEX40.fullmatch(e["merge"]))
            and relative(e.get("target")) and relative(e.get("backup")) and e.get("step") in STEPS
            and all(isinstance(e.get(k), str) and HEX64.fullmatch(e[k]) for k in ("expected_old_sha", "new_sha"))
            and (e.get("parent") is None or (isinstance(e["parent"], list) and len(e["parent"]) == 2
                                             and all(isinstance(i, int) for i in e["parent"]))))


def persisted(home):
    """The cursor and the journal as stored, for the digest (N5); invalid state is reported, not raised."""
    s = State(home)
    try:
        return {"cursor": s.applied(), "journal": s.journal(), "state": str(s.dir)}
    except InvalidState as e:
        return {"cursor": None, "journal": [], "state": str(s.dir), "state_error": str(e)}


def unresolved(entries):
    return [e for e in entries if e.get("step") != "clean"]


# ---------------------------------------------------------------- apply

class Run:
    def __init__(self, home, state, reader, run_id, journal):
        self.home, self.state, self.reader, self.run_id = str(home), state, reader, run_id
        self.journal = journal

    def save(self):
        self.state.save_journal(self.journal)

    def classify(self, parent, commit, targets):
        """{rel: (kind, live, parent identity, old, new)}"""
        out = {}
        for source, rel in targets:
            old, new = self.reader.blob(parent, source)[1], self.reader.blob(commit, source)[1]
            live, pid = snapshot(self.home, rel)
            out[rel] = (kind(live, old, new), live, pid, old, new)
        return out

    def write_target(self, commit, rel, live, pid, old, new):
        """One target step with SIGTERM and SIGALRM held: stage B in the backup, journal, re-walk, swap, check the
        displaced inode, dispose. Returns (ok, note)."""
        held = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGALRM})
        try:
            return self._write_target(commit, rel, live, pid, old, new)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, held)

    def _write_target(self, commit, rel, live, pid, old, new):
        parts = rel.split("/")
        name, backup_parts = parts[-1], ["backup", self.run_id, commit[:12], *parts[:-1]]
        (self.state.dir.joinpath(*backup_parts)).mkdir(parents=True, exist_ok=True, mode=0o700)
        bfd = walk(str(self.state.dir), backup_parts)
        pfd = None
        try:
            b_ino = stage_backup(bfd, name, new)
            entry = {"run": self.run_id, "merge": commit, "target": rel, "backup": "/".join([*backup_parts, name]),
                     "expected_old_sha": sha(old), "new_sha": sha(new), "parent": pid, "step": "staged"}
            self.journal.append(entry)
            self.save()

            def unstage(note):
                # nothing left the live path: remove our staged file (checked by inode) and the entry
                cur = look(bfd, name)
                if cur.get("ino") == b_ino:
                    os.unlink(name, dir_fd=bfd)
                self.journal.remove(entry)
                self.save()
                return False, note

            try:
                pfd = walk(self.home, parts[:-1])
            except WalkError as e:
                return unstage(f"parent changed before the swap: {e.strerror}")
            if ident(pfd) != pid:
                return unstage("parent changed before the swap")
            try:
                exchange(bfd, name, pfd, name)
            except OSError as e:
                return unstage(f"swap failed: {e}")
            entry["step"] = "swapped"
            self.save()
            got = look(bfd, name)
            if got.get("type") == "file" and got.get("mode") == MODE and sha(got["bytes"]) == entry["expected_old_sha"]:
                if self.parent_is(parts, pid):
                    entry["step"] = "clean"
                    self.save()
                    return True, "written"
                entry.update(step="unresolved", note="parent changed after the swap")
                self.save()
                return False, entry["note"]
            note = "live changed before the swap; " + self.swap_back(parts, pid, bfd, name, b_ino, new)
            entry.update(step="unresolved", note=note)
            self.save()
            return False, note
        finally:
            os.close(bfd)
            if pfd is not None:
                os.close(pfd)

    def parent_is(self, parts, pid):
        try:
            fd = walk(self.home, parts[:-1])
        except WalkError:
            return False
        try:
            return ident(fd) == pid
        finally:
            os.close(fd)

    def swap_back(self, parts, pid, bfd, name, b_ino, new):
        """Best effort: only when the live entry is still our staged file; verified afterwards."""
        try:
            fd = walk(self.home, parts[:-1])
        except WalkError as e:
            return f"not swapped back: {e.strerror}"
        try:
            if ident(fd) != pid:
                return "not swapped back: parent changed"
            cur = look(fd, name)
            if not (cur.get("type") == "file" and cur.get("ino") == b_ino and cur.get("mode") == MODE
                    and cur.get("bytes") == new):
                return "not swapped back: live is no longer the staged file"
            try:
                exchange(fd, name, bfd, name)
            except OSError as e:
                return f"swap-back failed: {e}"
            after = look(bfd, name)
            if after.get("ino") == b_ino:
                return "swapped back; the live version is at the target again, the new one in the backup"
            return "swap-back unverified: the backup name no longer holds the staged file"
        finally:
            os.close(fd)

    def revalidate(self):
        """Before any write: every clean entry kept from an earlier run must still see its parent and the new blob
        at mode 0644; an entry that does not is unresolved. Returns those entries."""
        bad = []
        for e in self.journal:
            if e["step"] != "clean":
                continue
            live, pid = snapshot(self.home, e["target"])
            if not (pid == e["parent"] and live.get("type") == "file" and live.get("mode") == MODE
                    and sha(live["bytes"]) == e["new_sha"]):
                e.update(step="unresolved", note=f"changed since an earlier run wrote it ({describe(live)})")
                bad.append(e)
        return bad

    def recheck(self, commit, cls):
        """Before L advances: every target of the merge equals its new blob, and every journal entry of the merge
        still sees the same parent. Returns the targets that fail."""
        bad = []
        for rel, (_, _, _, _, new) in cls.items():
            live, pid = snapshot(self.home, rel)
            mine = [e for e in self.journal if e["merge"] == commit and e["target"] == rel]
            if not (live.get("type") == "file" and live.get("mode") == MODE and live["bytes"] == new
                    and all(e["parent"] == pid for e in mine)):
                bad.append(rel)
                for e in mine:
                    e.update(step="unresolved", note="changed after apply")
        if bad:
            self.save()
        return bad


def new_result():
    return {"status": None, "reason": None, "cursor": None, "head": None, "merges": [], "passed": 0, "journal": [],
            "decisions": [], "state": None}


def run(home, repo=None, *, deadline=None, budget=BUDGET, git="git", reader=None, head=None, url=None, check=False):
    """Apply pending merges along main's first parent after the cursor L (with check, only classify them and write
    nothing but the mirror). The stage ends at min(start + budget, deadline): every git call is bounded by it, and
    past it no further target step starts. Returns a structured result; refusals and stage errors are in it."""
    started = time.monotonic()
    stage_deadline = min(started + budget, deadline if deadline is not None else started + STANDALONE_DEADLINE)
    home = Path(home)
    state = State(home)
    res = new_result()
    res["state"] = str(state.dir)
    lock = None if check else state.lock()
    umask = os.umask(0o022)
    try:
        try:
            cursor, entries = state.applied(), state.journal()
        except InvalidState as e:
            res.update(status="error", reason=str(e), state_error=str(e))
            res["decisions"].append(f"apply: state invalid: {e} — fix or move the file aside; nothing was written")
            return res
        res.update(cursor=cursor, journal=entries)
        held = unresolved(entries)
        if held:  # reported before any fetch, so a fetch failure cannot hide it
            res["decisions"].append(journal_decision(held, state))
        if not check and lock is None:
            res.update(status="skipped", reason="another apply holds .apply.lock")
            return res
        if held:
            res.update(status="blocked", reason="unresolved journal entries")
            return res
        try:
            if reader is None:
                reader, head = sync_mirror(state.dir, url or public_url(repo, git, git_env(state.dir), stage_deadline),
                                           git, stage_deadline)
            head = head or reader.resolve("refs/heads/main")
            res["head"] = head
            _apply(home, state, reader, head, cursor, entries, res, stage_deadline, check)
        except (ApplyError, OSError) as e:
            res.update(status="error", reason=f"{type(e).__name__}: {e}" if isinstance(e, OSError) else str(e))
            res["decisions"].append(f"apply: {res['reason']}")
        try:
            res["journal"] = state.journal()
        except InvalidState as e:
            res["decisions"].append(f"apply: state invalid: {e}")
        return res
    finally:
        os.umask(umask)
        if lock:
            lock.close()


def journal_decision(entries, state):
    items = "; ".join(f"{e['target']} (live ~/{e['target']}, backup {state.dir / e['backup']}): "
                      f"{e.get('note') or e.get('step')}" for e in entries)
    return f"apply: journal unresolved: {items} — check both versions, then cycle.py resolve --yes"


def owner_options(commit):
    return f"owner applies: pull, make apply, then cycle.py adopt {commit}"


def chain_after(reader, head, base):
    """First-parent commits after base up to head, oldest first; None when base is not on that chain."""
    rows = reader.first_parents(head)
    shas = [s for s, _ in rows]
    if base not in shas:
        return None
    return list(reversed(rows[:shas.index(base)]))


def differing(reader, commit, home):
    """v1 targets whose live state is not the blob at commit."""
    out = []
    for mode, path in reader.files(commit, ROOTS):
        rel = plain_target(path)
        if rel is None or mode != "100644":
            continue
        live, _ = snapshot(str(home), rel)
        if not (live.get("type") == "file" and live.get("mode") == MODE
                and live["bytes"] == reader.blob(commit, path)[1]):
            out.append(rel)
    return out


def _apply(home, state, reader, head, cursor, entries, res, stage_deadline, check):
    if cursor is None:
        diff = differing(reader, head, home)
        res.update(status="baseline-missing", reason="no applied.json", differing=diff)
        res["decisions"].append(f"apply: no applied commit yet; live differs from {head[:8]} on "
                                f"{', '.join(diff) or 'nothing'} — after checking, cycle.py adopt {head}")
        return
    chain = chain_after(reader, head, cursor["commit"])
    if chain is None:
        res.update(status="error", reason=f"cursor {cursor['commit'][:8]} is not on main's first-parent chain")
        res["decisions"].append(f"apply: {res['reason']} — cycle.py adopt <sha> after checking")
        return
    # clean entries: of the cursor (it advanced before the journal was cleared) are dropped; of the next candidate
    # they are revalidated before the cursor passes it (N1); of any other merge they block
    entries = [e for e in entries if e["merge"] != cursor["commit"]]
    if entries:
        first = next((c for c, p in chain if is_candidate(reader, p, c)), None)
        stray = [e for e in entries if e["merge"] != first]
        if stray:
            res.update(status="blocked", reason="journal entries of a merge that is not next")
            res["decisions"].append(journal_decision(stray, state))
            return
    r = Run(home, state, reader, f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{os.urandom(3).hex()}", entries)
    stale = r.revalidate()  # H1: nothing is written over a version an earlier run did not leave there
    if not check and (stale or entries != state.journal()):
        r.save()
    if stale:
        res.update(status="blocked", reason="a target written by an earlier run changed")
        res["decisions"].append(journal_decision(stale, state))
        return
    res["status"] = "would apply" if check else "ok"
    predicted = False  # check: only the next candidate is a prediction
    position = reached = cursor["commit"]
    wrote = False

    def advance():
        nonlocal position, wrote
        if reached != position:
            state.write("applied.json", {"commit": reached, "at": utc_now(), "by": "cycle" if wrote else "observed",
                                         "run": r.run_id})
            r.journal = [e for e in r.journal if e["merge"] != reached]
            r.save()
            res["cursor"] = state.applied()
            position, wrote = reached, False

    try:
        for commit, parent in chain:
            if not is_candidate(reader, parent, commit):
                res["passed"] += 1
                if not check:
                    reached = commit
                continue
            subject = reader.subject(commit)
            m = {"commit": commit, "pr": pr_of(subject), "subject": subject, "status": None, "targets": {}}
            res["merges"].append(m)
            label = f"{m['pr'] or ''} ({commit[:8]})".strip()
            if not check and time.monotonic() > stage_deadline:
                m.update(status="pending", reason="stage deadline passed; the next run continues")
                res["status"] = "partial"
                break
            later = check and predicted
            predicted = True
            if later:
                m["note"] = "compared with the current live snapshot (not a prediction)"
            targets, reason = assess(reader, parent, commit)
            if reason:
                m.update(status="refused", reason=reason)
                if not later:
                    res["decisions"].append(f"apply: {label} refused as a whole: {reason} — {owner_options(commit)}")
                if check:
                    continue
                res["status"] = "stopped"
                break
            cls = r.classify(parent, commit, targets)
            m["targets"] = {rel: c[0] if c[0] != "conflict" else f"conflict: {describe(c[1])}"
                            for rel, c in cls.items()}
            conflicts = [rel for rel, c in cls.items() if c[0] == "conflict"]
            if conflicts:
                m.update(status="conflict", reason="live differs from both sides")
                if not later:
                    res["decisions"].append(
                        f"apply: {label} not applied: live differs from both sides on "
                        + ", ".join(f"{t} ({describe(cls[t][1])})" for t in conflicts)
                        + f" — put the live edit into a PR, or {owner_options(commit)}")
                if check:
                    continue
                res["status"] = "stopped"
                break
            if check:
                m["status"] = "applicable"
                continue
            failed = expired = None
            for rel, (k, live, pid, old, new) in cls.items():
                if k != "write":
                    continue
                if time.monotonic() > stage_deadline:
                    expired = rel
                    break
                ok, note = r.write_target(commit, rel, live, pid, old, new)
                m["targets"][rel] = "written" if ok else f"failed: {note}"
                wrote = wrote or ok
                if not ok:
                    failed = (rel, note)
                    break
            if expired:
                m.update(status="partial", reason=f"stage deadline passed before {expired}; the next run continues")
                res["status"] = "partial"
                break
            if failed:
                written = any(v == "written" for v in m["targets"].values())
                m.update(status="partial" if written else "conflict", reason=f"{failed[0]}: {failed[1]}")
                held = unresolved(r.journal)
                res["decisions"].append(f"apply: {label} stopped at {failed[0]}: {failed[1]} — "
                                        + (journal_decision(held, state) if held else "the next run retries it"))
                res["status"] = "stopped"
                break
            bad = r.recheck(commit, cls)
            if bad:
                m.update(status="changed after apply", reason=", ".join(bad))
                held = unresolved(r.journal)
                res["decisions"].append(f"apply: {label} changed after apply on {', '.join(bad)}; cursor held — "
                                        + (journal_decision(held, state) if held else owner_options(commit)))
                res["status"] = "stopped"
                break
            m["status"] = "applied" if any(v == "written" for v in m["targets"].values()) else "done"
            reached = commit
            advance()
    finally:
        if not check:
            advance()
    if check and res["merges"] and res["merges"][0]["status"] in ("refused", "conflict"):
        res["status"] = "would stop"


# ---------------------------------------------------------------- owner commands

def adopt(home, repo, commit, *, git="git", reader=None, head=None, url=None, deadline=None, out=print):
    """Record commit as the applied commit by the owner, after printing what it skips (L4, N4)."""
    state = State(home)
    lock = state.lock()
    if lock is None:
        raise ApplyError("another apply holds .apply.lock")
    try:
        entries = state.journal()
        if unresolved(entries):
            raise ApplyError("the journal is unresolved; run resolve first")
        if reader is None:
            reader, head = sync_mirror(state.dir, url or public_url(repo, git, git_env(state.dir), deadline), git,
                                       deadline)
        head = head or reader.resolve("refs/heads/main")
        commit = reader.resolve(commit)
        cursor = state.applied()
        rows = reader.first_parents(head)
        shas = [s for s, _ in rows]
        if commit not in shas:
            raise ApplyError(f"{commit[:8]} is not on main's first-parent chain at {head[:8]}")
        if cursor is not None:
            chain = chain_after(reader, head, cursor["commit"])
            if chain is None or commit not in [c for c, _ in chain]:
                raise ApplyError(f"{commit[:8]} is not after the cursor {cursor['commit'][:8]} on main's first parent")
            skipped = chain[:[c for c, _ in chain].index(commit) + 1]
        else:
            skipped = []
        out(f"cursor: {cursor['commit'] if cursor else 'none'} -> {commit}")
        for c, p in skipped:
            if not is_candidate(reader, p, c):
                continue
            out(f"{'acknowledges' if c == commit else 'skips'} {c[:8]} {reader.subject(c)}")
            targets, reason = assess(reader, p, c)
            if reason:
                out(f"  refused: {reason}")
            for source, rel in targets or []:
                live, _ = snapshot(str(home), rel)
                out(f"  {rel}: {kind(live, reader.blob(p, source)[1], reader.blob(c, source)[1])}")
            sources = {source for source, _ in targets or []}
            out(f"  other paths: {', '.join(path for _, path in reader.changes(p, c) if path not in sources) or 'none'}")
        diff = differing(reader, commit, home)
        out(f"live differs from {commit[:8]} on: {', '.join(diff) or 'nothing'}")
        state.write("applied.json", {"commit": commit, "at": utc_now(), "by": "owner", "run": None})
        # entries of merges at or before the adopted commit are acknowledged with it; later ones stay
        order = {s: i for i, s in enumerate(shas)}  # newest first
        kept = [e for e in entries if order.get(e["merge"], -1) < order[commit]]
        if kept != entries:
            state.save_journal(kept)
        return {"adopted": commit, "differing": diff}
    finally:
        lock.close()


def describe_path(root, rel):
    live, _ = snapshot(root, rel)
    if live.get("type") != "file":
        return describe(live)
    return f"file {live['mode']:04o} sha256 {sha(live['bytes'])}"


def resolve(home, yes=False, out=print):
    """Print each journal entry with both paths; --yes clears the journal and nothing else."""
    state = State(home)
    lock = state.lock()
    if lock is None:
        raise ApplyError("another apply holds .apply.lock")
    try:
        entries = state.journal()
        for e in entries:
            out(f"{e['merge'][:8]} {e['target']} [{e.get('step')}] {e.get('note') or ''}".rstrip())
            out(f"  live   ~/{e['target']}: {describe_path(str(home), e['target'])}")
            out(f"  backup {state.dir / e['backup']}: {describe_path(str(state.dir), e['backup'])}")
            out(f"  expected old sha256 {e['expected_old_sha']}")
            out(f"  new sha256          {e['new_sha']}")
        if not entries:
            out("journal: empty")
        elif yes:
            state.save_journal([])
            out(f"journal cleared ({len(entries)} entries); files are left as they are")
        else:
            out("nothing changed; rerun with --yes to clear the journal")
        return {"entries": len(entries), "cleared": bool(entries and yes)}
    finally:
        lock.close()


# ---------------------------------------------------------------- CLI

def report(res, out=print):
    c = res.get("cursor")
    out(f"head: {res.get('head') or 'unknown'}")
    out(f"cursor: {c['commit']} by {c['by']} at {c['at']}" if c else "cursor: none (no applied.json)")
    out(f"journal: {len(res['journal'])} entries, {len(unresolved(res['journal']))} unresolved")
    out(f"status: {res['status']}" + (f" ({res['reason']})" if res.get("reason") else ""))
    if "differing" in res:
        out(f"live differs from head on: {', '.join(res['differing']) or 'nothing'}")
    out(f"non-candidate commits passed: {res['passed']}")
    for m in res["merges"]:
        out(f"{m['commit'][:8]} {m['pr'] or ''} {m['status']}" + (f": {m['reason']}" if m.get("reason") else "")
            + (f" [{m['note']}]" if m.get("note") else ""))
        for t, k in m["targets"].items():
            out(f"  {t}: {k}")
    for d in res["decisions"]:
        out(f"decision: {d}")


RECENT = 10


def recent(reader, head, home, count=RECENT, out=print):
    """With no cursor: the last count candidates, each compared with the live snapshot (informational)."""
    shown = 0
    for commit, parent in reader.first_parents(head):
        if shown >= count:
            break
        if not is_candidate(reader, parent, commit):
            continue
        shown += 1
        subject = reader.subject(commit)
        targets, reason = assess(reader, parent, commit)
        if reason:
            out(f"{commit[:8]} {pr_of(subject) or ''} refused: {reason}")
            continue
        out(f"{commit[:8]} {pr_of(subject) or ''} v1:")
        for source, rel in targets:
            live, _ = snapshot(str(home), rel)
            k = kind(live, reader.blob(parent, source)[1], reader.blob(commit, source)[1])
            out(f"  {rel}: {k}" + (f" ({describe(live)})" if k == "conflict" else ""))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true", required=True)
    p.add_argument("--home", type=Path, default=Path.home())
    p.add_argument("--repo", type=Path, help="the checkout whose origin URL is fetched (default: chezmoi's)")
    args = p.parse_args(argv)
    home = args.home.expanduser()
    try:
        started = time.monotonic()
        state = State(home)
        reader, head = sync_mirror(state.dir, public_url(args.repo or ready.source_repo(), env=git_env(state.dir)))
        res = run(home, check=True, reader=reader, head=head)
        report(res)
        if res.get("cursor") is None and res["status"] == "baseline-missing":
            print(f"recent candidates (last {RECENT}, compared with the current live snapshot, not a prediction):")
            recent(reader, head, home)
        print(f"secs: {time.monotonic() - started:.1f}")
        return 2 if res["status"] == "error" else 1 if res["decisions"] else 0
    except ApplyError as e:
        print(f"kaizen apply: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
