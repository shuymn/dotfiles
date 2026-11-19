"""Readiness checks R1-R5 of the kaizen daily cycle (docs/kaizen.md §6). Every check reads only; each command it runs
has its own timeout, and a command that fails, times out or is missing fails its check.

R1  `chezmoi diff` is empty for the live targets whose source path matches .claude/kaizen-managed of the checkout
    chezmoi is configured with (`chezmoi source-path`, its parent). Owner.
R2  the cycle's launchd job is loaded (`launchctl print gui/<uid>/<label>`) and every absolute path in its program
    and arguments (words of a `sh -c` string included) exists. Owner.
R3  `<home>/.claude/hooks/attention-budget.py status` shows no OVER line. An improver candidate.
R4  every observation source read without failure (gh may be off) and `gh auth status` passes (owner when not).
R5  the last run recorded before today (K/runs/<date>.json, its finished time) completed at most 3 days ago, and every
    open PR of the dotfiles repository whose head branch starts with kaizen/ is at most 14 days old.
Each result: {"status": "PASS"|"FAIL", "detail": str or list, "owner": bool}.
"""
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from fnmatch import fnmatchcase
from pathlib import Path

LABEL = "org.nix-community.home.kaizen-cycle"
RUN_DAYS, PR_DAYS = 3, 14
ABSOLUTE = re.compile(r"(?<![^\s'\"=])/[^\s'\";&|]+")  # an absolute path at the start of a shell word


def result(ok, detail, owner=False):
    return {"status": "PASS" if ok else "FAIL", "detail": detail, "owner": owner and not ok}


def run(argv, timeout, **kw):
    """(returncode or None, stdout, stderr tail); None when the command is missing or timed out."""
    try:
        p = subprocess.run(argv, timeout=timeout, capture_output=True, text=True, stdin=subprocess.DEVNULL, **kw)
    except FileNotFoundError as e:
        return None, "", str(e)
    except subprocess.TimeoutExpired:
        return None, "", f"{argv[0]} timed out after {timeout}s"
    return p.returncode, p.stdout, p.stderr.strip()[-300:]


def pattern_match(pattern, path):
    """Segment-wise glob where "**" stands for any number of segments (the merge-pr list syntax)."""
    def seg(p, parts):
        if not p:
            return not parts
        if p[0] == "**":
            return any(seg(p[1:], parts[i:]) for i in range(len(parts) + 1))
        return bool(parts) and fnmatchcase(parts[0], p[0]) and seg(p[1:], parts[1:])
    return seg(pattern.split("/"), path.split("/"))


def source_repo(chezmoi="chezmoi"):
    """The checkout chezmoi is configured with (the parent of its source directory), or None."""
    code, out, _ = run([chezmoi, "source-path"], 30)
    return Path(out.strip()).parent if code == 0 and out.strip() else None


def check_r1(home, repo, chezmoi="chezmoi"):
    if repo is None:
        return result(False, "chezmoi source-path failed", True)
    try:
        patterns = [l.strip() for l in (repo / ".claude/kaizen-managed").read_text().splitlines()
                    if l.strip() and not l.lstrip().startswith("#")]
    except OSError as e:
        return result(False, f"managed list unreadable: {e}", True)
    base = [chezmoi, "--destination", str(home)]
    code, out, err = run(base + ["managed", "--include=files,symlinks", "--path-style=all", "--format=json"], 60)
    if code != 0:
        return result(False, f"chezmoi managed failed: {err}", True)
    targets = sorted(e["absolute"] for e in json.loads(out).values()
                     if e.get("sourceAbsolute") and any(pattern_match(p, os.path.relpath(e["sourceAbsolute"], repo))
                                                        for p in patterns))
    if not targets:
        return result(False, "no managed target matches the managed list", True)
    code, out, err = run(base + ["diff", "--no-pager", "--exclude=scripts", *targets], 120)
    if code != 0:
        return result(False, f"chezmoi diff failed: {err}", True)
    differ = sorted(set(re.findall(r"^diff --git a/(\S+)", out, re.M)))
    return result(not differ, differ or f"{len(targets)} targets match", True)


def parse_launchctl(text):
    """(program, arguments) from `launchctl print` output."""
    m = re.search(r"^\s*program = (.+)$", text, re.M)
    args = re.search(r"^\s*arguments = \{\n(.*?)^\s*\}", text, re.M | re.S)
    return (m.group(1).strip() if m else None,
            [a.strip() for a in args.group(1).splitlines() if a.strip()] if args else [])


def check_r2(launchctl="launchctl", label=LABEL):
    code, out, err = run([launchctl, "print", f"gui/{os.getuid()}/{label}"], 10)
    if code != 0:
        return result(False, f"{label} is not loaded: {err or out.strip()[-200:]}", True)
    program, args = parse_launchctl(out)
    if program is None:
        return result(False, f"no program in launchctl print {label}", True)
    # Home Manager wraps the program as /bin/sh -c "/bin/wait4path /nix/store && exec <program> <args>"
    paths = dict.fromkeys(p for a in [program, *args] for p in ABSOLUTE.findall(a))
    missing = [p for p in paths if not os.path.exists(p)]
    return result(not missing, [f"missing: {p}" for p in missing] or f"loaded; program {program}", True)


def check_r3(home):
    code, out, err = run([str(home / ".claude/hooks/attention-budget.py"), "status"], 60)
    over = [l for l in out.splitlines() if l.startswith("OVER:")]
    if code not in (0, 1) or (code == 1 and not over):
        return result(False, f"attention-budget.py status failed ({code}): {err}")
    return result(not over, over or "no OVER")


def check_r4(sources, gh="gh"):
    bad = [f"source {n} {s.get('status')}: {s.get('error', '')}" for n, s in sources.items()
           if s.get("status") != "ok" and not (n == "gh" and s.get("status") == "off")]
    code, _, err = run([gh, "auth", "status"], 30)
    if code != 0:
        bad.append(f"gh auth status failed: {err}")
    return result(not bad, bad or "sources ok; gh authenticated", code != 0)


def check_r5(k, today, now, repo_slug, gh="gh"):
    bad, notes = [], []
    finished = []
    for f in sorted((k / "runs").glob("*.json")):
        if f.stem >= today:
            continue
        try:
            done = datetime.fromisoformat(json.loads(f.read_text())["finished"].replace("Z", "+00:00"))
            if done.tzinfo and done <= now:
                finished.append(done)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            notes.append(f"runs/{f.name} has no finished time")
    if finished:
        age = now - max(finished)
        if age > timedelta(days=RUN_DAYS):
            bad.append(f"last run finished {age.days} days ago")
    else:
        notes.append("first run")
    if repo_slug is None:
        bad.append("open kaizen PRs unknown: no GitHub origin for the dotfiles checkout")
    else:
        code, out, err = run([gh, "pr", "list", "-R", repo_slug, "--state", "open", "--limit", "200", "--json",
                              "number,headRefName,createdAt"], 60)
        try:
            if code != 0:
                raise ValueError(err)
            for pr in json.loads(out):
                created = datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
                if pr["headRefName"].startswith("kaizen/") and now - created > timedelta(days=PR_DAYS):
                    bad.append(f"open PR #{pr['number']} ({pr['headRefName']}) is {(now - created).days} days old")
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            bad.append(f"open kaizen PRs unknown: {e}")
    return result(not bad, bad + notes if bad else "; ".join(notes) or "alive")
