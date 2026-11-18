#!/usr/bin/env python3
"""Claude Code PreToolUse hook: deny actions that used to rest on an agent remembering a rule.

- A session running in a delegated worktree (~/.t3/worktrees/..., or a subagent's <repo>-worktrees/agent-*) never writes outside it: no git push, no gh writes,
  no wrangler deploys or secrets, no package publishing. The orchestrator does those.
- No command or file read shows a secret file under ~/.t3/userdata/secrets; passing one as "$(cat <file>)" to a
  command is allowed, since that is how a secret delivered as a file is used.
- Pencil's AI generation (Generate) is never called: the owner's quota is small.
- A gh write (PR, issue, release, API) carries no local paths in its command or its body file.
- A PR is merged only through ~/.claude/bin/merge-pr, which merges the checked head once every check on it passed and
  refuses to run in a delegated worktree.
"""

import json
import os
import re
import sys

SECRETS = ".t3/userdata/secrets"
WORKTREES = os.path.join(os.path.expanduser("~"), ".t3", "worktrees") + os.sep
AGENT_WORKTREE = re.compile(r"-worktrees/agent-[^/]+/")  # Claude Code subagent worktrees made by `git wt`

GH_READ = re.compile(
    r"^gh\s+(?:(?:pr|issue|run|release|repo|workflow|label|search)\s+(?:view|list|diff|checks|status|watch|download)\b"
    r"|search\b|auth\s+status\b|--version\b|help\b)"
)
GH_API_WRITE = re.compile(r"(?:^|\s)(?:-X|--method)\s*(?!GET\b)[A-Z]+|(?:^|\s)(?:-f|-F|--field|--raw-field|--input)(?:\s|=)")
WRANGLER_WRITE = re.compile(r"\bwrangler\s+(?:deploy|publish|secret|versions\s+(?:deploy|upload)|rollback|delete|r2|kv|d1|queues)\b")
PUBLISH = re.compile(r"\b(?:npm|pnpm|yarn|bun|cargo|deno)\s+publish\b")
GIT_PUSH = re.compile(r"\bgit\b(?:\s+-[Cc]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+push\b")
CAT_SUBST = re.compile(r"\"?\$\((?:cat\s+|<\s*)[\"']?[^\"')]*" + re.escape(SECRETS) + r"[^\"')]*[\"']?\)\"?")
LOCAL_PATH = re.compile(r"(?:/Users|/home)/[A-Za-z0-9._-]+/|\.t3/(?:scratch|worktrees|userdata)/|/tmp/claude-\d+/|/private/var/folders/")
REPO_OPT = r"(?:(?:-R|--repo)[ =]\S+\s+)?"
GH_PR_MERGE = re.compile(rf"^gh\s+{REPO_OPT}pr\s+{REPO_OPT}merge\b")
PENCIL_GENERATE = re.compile(r"\bgenerate\w*\s*\(", re.IGNORECASE)


def deny(reason: str) -> None:
    json.dump(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}},
        sys.stdout,
    )
    sys.exit(0)


def segments(command: str):
    for part in re.split(r"&&|\|\||[;|\n]|\$\(|`", command):
        part = part.strip().lstrip("(").strip()
        part = re.sub(r"^(?:env\s+)?(?:\w+=\S*\s+)*", "", part)
        part = re.sub(r"^(?:command|builtin|nohup|nice|time|mise\s+exec\s+--|pnpm\s+exec|npx|bunx)\s+", "", part)
        if part:
            yield part


def code_only(command: str) -> str:
    """The command without heredoc bodies and quoted strings, so text that only mentions a command does not match."""
    command = command.replace("\\\n", " ")
    command = re.sub(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2(?=\n|$)", " ", command, flags=re.S)
    return re.sub(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"", "''", command)


def check_public_text(command: str, cwd: str) -> None:
    """A gh write publishes its body: it must carry no local paths."""
    write = re.compile(r"^gh\s+(?:(?:pr|issue|release)\s+(?:create|edit|comment|review)\b|api\b)")
    file_arg = re.compile(r"(?:--body-file|-F|--input)[ =]+(\"[^\"]+\"|'[^']+'|\S+)")
    redirect = re.compile(r"\d?>>?\s*\S+")
    # Only the gh write itself is published: other commands in the line, redirections and the body file's path are not.
    writes = [redirect.sub("", seg) for seg in segments(command) if write.match(seg)]
    if not writes:
        return
    texts = [file_arg.sub("", seg) for seg in writes]  # the file's path is not published; its content is
    for m in (m for seg in writes for m in file_arg.finditer(seg)):
        path = os.path.expanduser(m.group(1).strip("\"'"))
        if path != "-":
            try:
                with open(os.path.join(cwd, path), encoding="utf-8", errors="replace") as f:
                    texts.append(f.read(1_000_000))
            except OSError:
                pass
    for text in texts:
        hit = LOCAL_PATH.search(text)
        if hit:
            deny(f"Public text must not contain local paths ({hit.group(0)!r}). Use repository-relative paths or leave it out.")


def check_bash(command: str, cwd: str) -> None:
    if SECRETS in CAT_SUBST.sub("", command):
        deny(f"Commands must not show files under ~/{SECRETS}. Pass a secret file only as \"$(cat <file>)\" to the command that needs it.")
    check_public_text(command, cwd)
    delegated = (cwd + os.sep).startswith(WORKTREES) or AGENT_WORKTREE.search(cwd + os.sep)
    reason = "External writes belong to the orchestrator: report the command you would run instead of running it."
    if not delegated:  # a delegated worktree's `gh pr merge` falls under its gh write rule below
        for seg in segments(code_only(command)):
            if GH_PR_MERGE.match(seg) and not re.search(r"\s(?:--help|-h)\b", seg):
                deny("Merge with ~/.claude/bin/merge-pr <pr> <head-sha> [--merge|--squash|--rebase]: it merges only that "
                     "head, once every check on it passed, and reads the result back.")
        return
    if "merge-pr" in command:  # merge-pr checks its own checkout; this also covers a `cd` out of the worktree first
        deny(reason)
    for seg in segments(command):
        if GIT_PUSH.search(seg) or WRANGLER_WRITE.search(seg) or PUBLISH.search(seg):
            deny(reason)
        if re.match(r"^gh\b", seg):
            if re.match(r"^gh\s+api\b", seg):
                if GH_API_WRITE.search(seg):
                    deny(reason)
            elif not GH_READ.match(seg):
                deny(reason)


def main() -> None:
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    tin = data.get("tool_input") or {}
    if tool == "Bash":
        check_bash(tin.get("command", ""), data.get("cwd", ""))
    elif tool in ("Read", "Grep", "Glob", "NotebookRead"):
        target = " ".join(str(tin.get(k, "")) for k in ("file_path", "path", "pattern"))
        if SECRETS in target:
            deny(f"Files under ~/{SECRETS} must not be read into the conversation.")
    elif tool.startswith("mcp__pencil__"):
        text = json.dumps(tin)
        if PENCIL_GENERATE.search(text):
            deny("Pencil's Generate (AI image/SVG) is not used: the quota is small. Draw icons as paths (Octicons). "
                 "If this matched a helper of your own named generate*, rename it.")


if __name__ == "__main__":
    main()
