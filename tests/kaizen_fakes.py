"""Fake commands for the weekly stage's tests: git, claude, gh, codex, ssh-keygen and public-check, in one script.

Each fake is `fakes.py <tool> <dir> args...`. It appends {tool, argv, env, cwd, stdin, pid, pgid} to <dir>/log.jsonl
and acts from <dir>/scenario.json. git keeps a tiny object store in <dir>/db.json: blobs, flat trees ({path: [mode,
blob]}), commits, refs, temp indexes and the server's refs. No real git, claude, gh, codex or ssh-keygen runs.
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path

TOOL, DIR, ARGS = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]


def load(name, default):
    try:
        return json.loads((DIR / name).read_text())
    except FileNotFoundError:
        return default


def dump(name, value):
    tmp = DIR / f".{name}.{os.getpid()}"
    tmp.write_text(json.dumps(value))
    os.replace(tmp, DIR / name)


SCENARIO = load("scenario.json", {})
STDIN = b"" if sys.stdin is None or sys.stdin.closed else sys.stdin.buffer.read()
with open(DIR / "log.jsonl", "a") as f:
    f.write(json.dumps({"tool": TOOL, "argv": ARGS, "env": dict(os.environ), "cwd": os.getcwd(),
                        "stdin": STDIN.decode("utf-8", "replace"), "pid": os.getpid(), "pgid": os.getpgid(0)}) + "\n")


def out(data):
    sys.stdout.buffer.write(data if isinstance(data, bytes) else data.encode())


def sleep_with_grandchild(spec):
    if spec.get("grandchild"):
        child = subprocess.Popen(["sleep", "300"])
        Path(spec["grandchild"]).write_text(str(child.pid))
    if spec.get("pidfile"):
        Path(spec["pidfile"]).write_text(str(os.getpid()))
    time.sleep(spec.get("sleep", 0))


# ---------------------------------------------------------------- git

def oid(*parts):
    return hashlib.sha1("\0".join(map(str, parts)).encode()).hexdigest()


def blob_oid(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def git():
    db = load("db.json", {})
    args = list(ARGS)
    config = {}
    while args and args[0] in ("--git-dir", "-C", "-c"):
        if args[0] == "-c":
            k, _, v = args[1].partition("=")
            config[k] = v
        args = args[2:]
    cmd, rest = args[0], args[1:]
    commits, blobs = db.setdefault("commits", {}), db.setdefault("blobs", {})

    def rev(r):
        r = r.removesuffix("^{commit}")
        r = db.get("refs", {}).get(r, r)
        if r not in commits:
            sys.stderr.write(f"fatal: bad revision {r}\n")
            sys.exit(128)
        return r

    def tree(c):
        return commits[rev(c)]["tree"]

    def blob(o):
        return bytes.fromhex(blobs[o])

    fail = SCENARIO.get("git_fail", {}).get(cmd)
    if fail:
        sys.stderr.write(f"scripted failure of {cmd}\n")
        sys.exit(fail)
    if cmd == "clone":
        os.makedirs(rest[-1], exist_ok=True)
    elif cmd == "fetch":
        pass
    elif cmd == "remote":
        out(SCENARIO.get("origin", "git@github.com:o/r.git") + "\n")
    elif cmd == "rev-parse":
        out(rev(rest[-1]) + "\n")
    elif cmd == "archive":
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for path, (mode, o) in sorted(tree(rest[-1]).items()):
                info = tarfile.TarInfo(path)
                data = blob(o)
                if mode == "120000":
                    info.type, info.linkname = tarfile.SYMTYPE, data.decode()
                    tar.addfile(info)
                else:
                    info.size, info.mode = len(data), 0o755 if mode == "100755" else 0o644
                    tar.addfile(info, io.BytesIO(data))
        out(buf.getvalue())
    elif cmd == "ls-tree":
        flags = [a for a in rest if a.startswith("-") and a != "--"]
        pos = [a for a in rest if not a.startswith("-")]
        t = tree(pos[0])
        paths = rest[rest.index("--") + 1:] if "--" in rest else []
        rows = []
        if "-r" in flags:
            rows = [(m, "blob", o, p) for p, (m, o) in sorted(t.items())
                    if not paths or any(p == q or p.startswith(q + "/") for q in paths)]
        else:
            for q in paths or [""]:
                if q and not q.endswith("/") and q in t:
                    rows.append((t[q][0], "blob", t[q][1], q))
                    continue
                prefix = q if q.endswith("/") or not q else None
                if prefix is None:
                    continue
                seen = set()
                for p, (m, o) in sorted(t.items()):
                    if p.startswith(prefix):
                        head = p[len(prefix):].split("/")[0]
                        full = prefix + head
                        if full in seen:
                            continue
                        seen.add(full)
                        rows.append((m, "blob", o, full) if full == p else ("040000", "tree", oid(full), full))
        out(b"".join(f"{m} {k} {o}\t{p}".encode() + b"\0" for m, k, o, p in rows))
    elif cmd == "cat-file":
        out(blob(rest[-1]))
    elif cmd == "diff":
        a, b = [r for r in rest if not r.startswith("-")][:2]
        ta, tb = tree(a), tree(b)
        rows = []
        for p in sorted(set(ta) | set(tb)):
            if p not in ta:
                rows.append(("A", p))
            elif p not in tb:
                rows.append(("D", p))
            elif ta[p] != tb[p]:
                rows.append(("M" if ta[p][0] == tb[p][0] else "T", p))
        out(b"".join(f"{s}\0{p}\0".encode() for s, p in rows))
    elif cmd == "log":
        out(commits[rev(rest[-1])]["message"].splitlines()[0] + "\n")
    elif cmd == "show":
        c, _, path = rest[-1].partition(":")
        t = tree(c)
        if path not in t:
            sys.stderr.write(f"fatal: path {path} does not exist\n")
            sys.exit(128)
        out(blob(t[path][1]))
    elif cmd == "config" and "--file" not in rest:
        out(SCENARIO.get("origin", "git@github.com:o/r.git") + "\n")  # remote.origin.url
    elif cmd == "config":
        file, key = rest[rest.index("--file") + 1], rest[-1]
        section = None
        for line in Path(file).read_text().splitlines():
            line = line.strip()
            if line.startswith("["):
                section = line.strip("[]")
            elif "=" in line and f"{section}.{line.split('=')[0].strip()}" == key:
                out(line.split("=", 1)[1].strip() + "\n")
                return db
        sys.exit(1)
    elif cmd in ("read-tree", "update-index", "write-tree"):
        index = db.setdefault("index", {})
        name = os.environ["GIT_INDEX_FILE"]
        if cmd == "read-tree":
            index[name] = dict(tree(rest[-1]))
        elif cmd == "update-index":
            mode, o, path = rest[-1].split(",", 2)
            index[name][path] = [mode, o]
        else:
            t = index[name]
            tid = oid("tree", json.dumps(t, sort_keys=True))
            db.setdefault("trees", {})[tid] = t
            out(tid + "\n")
    elif cmd == "hash-object":
        o = blob_oid(STDIN)
        blobs[o] = STDIN.hex()
        out(o + "\n")
    elif cmd == "commit-tree":
        parent = rest[rest.index("-p") + 1]
        message = Path(rest[rest.index("-F") + 1]).read_text()
        t = db["trees"][rest[-1]]
        c = oid("commit", parent, message, json.dumps(t, sort_keys=True))
        commits[c] = {"tree": t, "parents": [parent], "message": message, "config": config, "signed": "-S" in rest,
                      "env": {k: v for k, v in os.environ.items() if k.startswith("GIT_")}}
        out(c + "\n")
    elif cmd == "rev-list" and "rev_list_count" in SCENARIO:
        out(f"{SCENARIO['rev_list_count']}\n")
    elif cmd == "rev-list":
        a, b = rest[-1].split("..")
        a, b = rev(a), rev(b)
        n, c = 0, b
        while c and c != a:
            n += 1
            c = (commits[c]["parents"] or [None])[0]
        out(f"{n}\n")
    elif cmd == "push":
        spec = SCENARIO.get("push", {})
        sleep_with_grandchild(spec)
        lease = next(a for a in rest if a.startswith("--force-with-lease="))[len("--force-with-lease="):] \
            if any(a.startswith("--force-with-lease=") for a in rest) else None
        src, _, dst = rest[-1].partition(":")
        server = db.setdefault("server", {})
        if lease is not None and lease.endswith(":") and dst in server:
            sys.stderr.write(" ! [rejected] (stale info)\n")
            sys.exit(1)
        if spec.get("server", True):
            server[dst] = src
            dump("db.json", db)
        if spec.get("code"):
            sys.exit(spec["code"])
    elif cmd == "ls-remote":
        ref = rest[-1]
        if ref in db.get("server", {}):
            out(f"{db['server'][ref]}\t{ref}\n")
    else:
        sys.stderr.write(f"fake git: unexpected {ARGS}\n")
        sys.exit(2)
    return db


# ---------------------------------------------------------------- the others

def step(name):
    """The next scripted answer of a tool: a list is consumed in order, its last item repeating."""
    calls = load("calls.json", {})
    n = calls.get(name, 0)
    calls[name] = n + 1
    dump("calls.json", calls)
    spec = SCENARIO.get(name, {})
    return spec[min(n, len(spec) - 1)] if isinstance(spec, list) else spec


def claude():
    if ARGS[:2] == ["auth", "status"]:
        sys.exit(SCENARIO.get("auth_code", 0))
    spec = step("claude")
    for path, text in spec.get("edits", {}).items():
        Path(path).write_text(text)
    for path in spec.get("create", []):
        Path(path).write_text("new\n")
    for path in spec.get("chmod", []):
        os.chmod(path, 0o755)
    for path, target in spec.get("symlink", {}).items():
        os.unlink(path)
        os.symlink(target, path)
    found = [m for m in SCENARIO.get("markers", []) for top, _, files in os.walk(".") for n in files
             if not os.path.islink(os.path.join(top, n)) and m.encode() in Path(top, n).read_bytes()]
    dump("scan.json", found)
    sleep_with_grandchild(spec)
    if "raw" in spec:
        out(spec["raw"])
    else:
        result = {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 1.25,
                  **spec.get("result", {})}
        out(json.dumps(result))
    sys.exit(spec.get("code", 0))


def gh():
    if ARGS[:2] == ["pr", "create"]:
        spec = step("create")
        with open(DIR / "created.jsonl", "a") as f:
            f.write(json.dumps({"argv": ARGS, "body": Path(ARGS[ARGS.index("--body-file") + 1]).read_bytes().hex()})
                    + "\n")
        if spec.get("server", True):  # the PR the server holds: head at what the branch points to now
            db = load("db.json", {})
            opt = lambda flag: ARGS[ARGS.index(flag) + 1]
            prs = db.setdefault("prs", [])
            number = int(spec.get("number", 9))
            prs.append({"number": number, "html_url": f"https://github.com/{opt('--repo')}/pull/{number}",
                        "state": "open", "base": {"ref": opt("--base")},
                        "head": {"ref": opt("--head"), "repo": {"full_name": spec.get("head_repo", opt("--repo"))},
                                 "sha": spec.get("head_sha") or db.get("server", {}).get(f"refs/heads/{opt('--head')}")}})
            dump("db.json", db)
        sleep_with_grandchild(spec)
        out(spec.get("stdout", ""))
        sys.exit(spec.get("code", 0))
    if ARGS[0] == "api":
        url = ARGS[-1]
        spec = step("open" if "state=open" in url else "lookup")
        if isinstance(spec, dict) and spec.get("sleep"):
            sleep_with_grandchild(spec)
        if spec == "fail" or (isinstance(spec, dict) and spec.get("code")):
            sys.stderr.write("gh: HTTP 502\n")
            sys.exit(1)
        if spec == "auto":  # the server's PRs for the head the query names, in one page
            head = url.split("head=")[1].split("&")[0].split(":", 1)[1]
            repo = url.split("repos/")[1].split("/pulls")[0]
            spec = [[p for p in load("db.json", {}).get("prs", [])
                     if p["head"]["ref"] == head and p["html_url"].startswith(f"https://github.com/{repo}/")]]
        out(json.dumps(spec))
        return
    if ARGS[0] == "auth":
        return
    sys.exit(SCENARIO.get("gh_code", 0))


def codex():
    spec = step("codex")
    sleep_with_grandchild(spec)
    for pattern, text in spec.get("tamper", {}).items():
        for path in Path("/").glob(pattern.lstrip("/")):
            with open(path, "a") as f:
                f.write(text)
    o = ARGS[ARGS.index("-o") + 1]
    if "verdict" in spec:
        Path(o).write_text(spec["verdict"] if isinstance(spec["verdict"], str) else json.dumps(spec["verdict"]))
    sys.exit(spec.get("code", 0))


def public_check():
    spec = step("public_check")
    body = ARGS[ARGS.index("--body-file") + 1]
    with open(DIR / "checked.jsonl", "a") as f:
        f.write(json.dumps({"argv": ARGS, "body": Path(body).read_bytes().hex(), "cwd": os.getcwd(),
                            "env": dict(os.environ)}) + "\n")
    sys.exit(spec.get("code", 0))


if __name__ == "__main__":
    if TOOL == "git":
        dump("db.json", git())
    elif TOOL == "ssh-keygen":
        sys.exit(SCENARIO.get("keygen_code", 0))
    else:
        {"claude": claude, "gh": gh, "codex": codex, "public-check": public_check}[TOOL]()
