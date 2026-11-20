"""Readiness checks R1-R5 of the kaizen daily cycle (docs/kaizen.md §6). Every check reads only; each command it runs
has its own timeout, and a command that fails, times out or is missing fails its check.

R1  `chezmoi diff` is empty for the live targets whose source path matches .claude/kaizen-managed of the checkout
    chezmoi is configured with (`chezmoi source-path`, its parent), pending removals of .chezmoiremove included (their
    source is that file). Owner.
R2  the cycle's launchd job is loaded (`launchctl print gui/<uid>/<label>`) and every absolute path in its program
    and arguments (words of a `sh -c` string included) exists. Owner.
R3  `<home>/.claude/hooks/attention-budget.py status` shows no OVER line. An improver candidate.
R4  every observation source read without failure (gh and t3 may be off) and `gh auth status` passes (owner when not).
R5  the published run (K/current/record.json, read before this run publishes) finished at most 3 days ago, and every
    open PR of the dotfiles repository whose head is its own branch starting with kaizen/ is at most 14 days old
    (open_kaizen_prs, which the weekly stage also uses).
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
    code, out, err = run(base + ["managed", "--include=files,symlinks,remove", "--path-style=all", "--format=json"],
                         60)
    if code != 0:
        return result(False, f"chezmoi managed failed: {err}", True)
    targets = []
    for e in json.loads(out).values():
        # a pending removal from .chezmoiremove comes with an empty sourceRelative and the source directory as its
        # sourceAbsolute; it belongs to that file, and `chezmoi diff` shows it as a deleted file
        source = e["sourceAbsolute"]
        source = source if e.get("sourceRelative") else os.path.join(source, ".chezmoiremove")
        if any(pattern_match(p, os.path.relpath(source, repo)) for p in patterns):
            targets.append(e["absolute"])
    targets.sort()
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
           if s.get("status") != "ok" and not (n in ("gh", "t3") and s.get("status") == "off")]
    code, _, err = run([gh, "auth", "status"], 30)
    if code != 0:
        bad.append(f"gh auth status failed: {err}")
    return result(not bad, bad or "sources ok; gh authenticated", code != 0)


def open_kaizen_prs(repo_slug, gh="gh", runner=None):
    """The open PRs of repo_slug (REST objects) whose head is a branch of that same repository starting with kaizen/;
    a fork's kaizen/ branch does not count. Every page is read. ValueError when gh fails or the answer is not pages of
    PRs. runner(argv) -> (returncode or None, stdout, stderr) replaces the default 60-second run."""
    argv = [gh, "api", "--paginate", "--slurp", f"repos/{repo_slug}/pulls?state=open&per_page=100"]
    code, out, err = runner(argv) if runner else run(argv, 60)
    if code != 0:
        raise ValueError(f"gh api pulls failed: {err}")
    return [pr for pr in slurped(out) if pr["head"]["ref"].startswith("kaizen/")
            and str((pr["head"].get("repo") or {}).get("full_name", "")).lower() == repo_slug.lower()]


def slurped(out):
    """The items of `gh api --paginate --slurp` output (a list of pages); ValueError for any other shape."""
    pages = json.loads(out)
    if not isinstance(pages, list) or not all(isinstance(p, list) for p in pages):
        raise ValueError("gh api: not a list of pages")
    return [pr for page in pages for pr in page]


def check_r5(k, now, repo_slug, gh="gh"):
    bad, notes = [], []
    try:
        done = datetime.fromisoformat(json.loads((k / "current/record.json").read_text())["finished"]
                                      .replace("Z", "+00:00"))
        if not done.tzinfo or done > now:
            raise ValueError(done)
        if now - done > timedelta(days=RUN_DAYS):
            bad.append(f"last run finished {(now - done).days} days ago")
    except FileNotFoundError:
        notes.append("first run")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        bad.append(f"last run unreadable: {e}")
    if repo_slug is None:
        bad.append("open kaizen PRs unknown: no GitHub origin for the dotfiles checkout")
    else:
        try:
            for pr in open_kaizen_prs(repo_slug, gh):
                created = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
                if now - created > timedelta(days=PR_DAYS):
                    bad.append(f"open PR #{pr['number']} ({pr['head']['ref']}) is {(now - created).days} days old")
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            bad.append(f"open kaizen PRs unknown: {e}")
    return result(not bad, bad + notes if bad else "; ".join(notes) or "alive")
