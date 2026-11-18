#!/usr/bin/env python3
# Claude Code PreToolUse(Bash) hook: ask before a force push or a push to main/master.
# In a repository with a pre-push hook, deny a push from a delegated worker's worktree while its tracked files have
# uncommitted changes (the worker is still editing, and pre-push would test that tree, not the pushed commits), and a
# push while another `git push` of the same repository (any of its worktrees) started in the last 30 minutes still runs
# (parallel pre-push runs time out). The scan narrows the window between sessions; it is not a lock.
# Other pushes pass through, so work branches and PRs can go out without a prompt.
# Any parse error lets the command through: this is a confirmation step, not a security boundary.
import json
import os
import re
import shlex
import subprocess
import sys

PROTECTED = {"main", "master"}
DELEGATED = re.compile(r"/\.t3/worktrees/|-worktrees/agent-[^/]+/")  # worktrees the orchestrator hands to workers
OPTS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}


def git_output(cwd, *args):
    try:
        out = subprocess.run(
            ["git", "-C", cwd, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def current_branch(cwd):
    return git_output(cwd, "symbolic-ref", "--short", "-q", "HEAD")


def has_pre_push(cwd):
    hooks = git_output(cwd, "config", "--get", "core.hooksPath")
    if hooks:
        hooks = os.path.expanduser(hooks)
        if not os.path.isabs(hooks):
            hooks = os.path.join(git_output(cwd, "rev-parse", "--show-toplevel") or cwd, hooks)
    else:
        hooks = git_output(cwd, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    return bool(hooks) and os.access(os.path.join(hooks, "pre-push"), os.X_OK)


def seconds(etime):
    days, _, rest = etime.rpartition("-")
    total = 0
    for part in rest.split(":"):
        total = total * 60 + int(part)
    return total + int(days or 0) * 86400


def process_cwd(pid):
    try:
        out = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return next((line[1:] for line in out.splitlines() if line.startswith("n")), None)


def running_push(common_dir):
    """A live `git push` of the repository with this common git dir, started within the last 30 minutes."""
    try:
        out = subprocess.run(["ps", "-axo", "pid=,stat=,etime=,command="], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4 or parts[1].startswith("Z") or os.path.basename(parts[3].split()[0]) != "git":
            continue
        toks, j, where = parts[3].split()[1:], 0, process_cwd(parts[0])
        while j < len(toks) and toks[j].startswith("-"):  # git has already applied -C to its own cwd
            j += 2 if toks[j] in ("-C", "-c") else 1
        if not (j < len(toks) and toks[j] == "push" and seconds(parts[2]) < 1800 and where):
            continue
        if git_output(where, "rev-parse", "--path-format=absolute", "--git-common-dir") == common_dir:
            return f"{parts[0]} {parts[3][:120]}"
    return None


def pre_push_block(cwd):
    if not has_pre_push(cwd):
        return None
    top = git_output(cwd, "rev-parse", "--show-toplevel") or cwd
    if DELEGATED.search(top + os.sep) and git_output(cwd, "status", "--porcelain", "--untracked-files=no"):
        return (f"{top} has uncommitted changes to tracked files: its worker is still editing, and pre-push would test "
                "that tree instead of the pushed commits. Push after the worker has reported and committed.")
    other = running_push(git_output(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    if other:
        return f"another git push is running (pid {other}); parallel pre-push runs time out. Push after it ends."
    return None


def push_reason(tokens, cwd):
    """tokens start right after `push`. Returns a reason string when the push needs a prompt."""
    opts, pos = [], []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in OPTS_WITH_VALUE:
            i += 2
            continue
        (opts if t.startswith("-") else pos).append(t)
        i += 1

    for o in opts:
        if (
            o in ("--force", "--force-if-includes", "--mirror")
            or o.startswith("--force-with-lease")
            or re.fullmatch(r"-[A-Za-z]*f[A-Za-z]*", o)
        ):
            return f"force push（{o}）"
        if o in ("--all", "--branches"):
            return f"全ブランチの push（{o}）"

    refspecs = pos[1:]
    if not refspecs:
        branch = current_branch(cwd)
        if branch in PROTECTED:
            return f"今のブランチ {branch} の push"
        return None
    for spec in refspecs:
        if spec.startswith("+"):
            return f"force push（{spec}）"
        dst = spec.split(":")[-1]
        # `:` pushes every matching branch and `*` is a pattern, so either can reach main.
        if not dst or "*" in dst:
            return f"複数ブランチの push（{spec}）"
        dst = dst.removeprefix("refs/heads/")
        if dst == "HEAD":
            dst = current_branch(cwd) or dst
        if dst in PROTECTED:
            return f"{dst} への push（{spec}）"
    return None


def check(command, cwd):
    """The strongest decision over every push in the command: a deny wins over an ask."""
    asked = None
    for seg in re.split(r"&&|\|\||;|\||\n", command):
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = seg.split()
        if not toks:
            continue
        if toks[0] == "cd" and len(toks) > 1:
            cwd = os.path.join(cwd, os.path.expanduser(toks[1]))
            continue
        if os.path.basename(toks[0]) != "git":
            continue
        j, git_cwd = 1, cwd
        while j < len(toks) and toks[j].startswith("-"):
            if toks[j] in ("-C", "-c") and j + 1 < len(toks):
                if toks[j] == "-C":
                    git_cwd = os.path.join(cwd, os.path.expanduser(toks[j + 1]))
                j += 2
            else:
                j += 1
        if j >= len(toks):
            continue
        sub, args = toks[j], toks[j + 1 :]
        if sub != "push":
            # Expand aliases such as `push-f = push --force-with-lease` from the user's gitconfig.
            alias = shlex.split(
                git_output(git_cwd, "config", "--get", f"alias.{sub}") or ""
            )
            if alias:
                sub, args = alias[0], alias[1:] + args
        if sub == "push" and not {"--help", "-h"} & set(args):
            block = pre_push_block(git_cwd)
            if block:
                return "deny", block
            reason = push_reason(args, git_cwd)
            if reason and not asked:
                asked = "ask", f"{reason}は取り消しにくいので確認します。作業ブランチへの push なら確認は要りません。"
    return asked


def main():
    try:
        data = json.load(sys.stdin)
        command = data.get("tool_input", {}).get("command") or ""
        if "push" not in command:
            return
        result = check(command, data.get("cwd") or os.getcwd())
    except Exception:  # noqa: BLE001 — fail open, see the header
        return
    if result:
        decision, reason = result
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": decision,
                        "permissionDecisionReason": reason,
                    }
                },
                ensure_ascii=False,
            )
        )


main()
