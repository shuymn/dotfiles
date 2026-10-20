#!/usr/bin/env python3
# Claude Code PreToolUse(Bash) hook: ask before a force push or a push to main/master.
# Other pushes pass through, so work branches and PRs can go out without a prompt.
# Any parse error lets the command through: this is a confirmation step, not a security boundary.
import json
import os
import re
import shlex
import subprocess
import sys

PROTECTED = {"main", "master"}
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
        if sub == "push":
            reason = push_reason(args, git_cwd)
            if reason:
                return reason
    return None


def main():
    try:
        data = json.load(sys.stdin)
        command = data.get("tool_input", {}).get("command") or ""
        if "push" not in command:
            return
        reason = check(command, data.get("cwd") or os.getcwd())
    except Exception:  # noqa: BLE001 — fail open, see the header
        return
    if reason:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": f"{reason}は取り消しにくいので確認します。作業ブランチへの push なら確認は要りません。",
                    }
                },
                ensure_ascii=False,
            )
        )


main()
