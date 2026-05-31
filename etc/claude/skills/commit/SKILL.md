---
name: commit
description: Creates meaningful git commits by analyzing changes and committing in logical units. Use when the user wants to commit changes to git, requests commit creation, or asks to save changes to version control. Supports --english and --japanese for commit language selection and --branch to create a new branch before committing.
allowed-tools: [Bash, Read, Grep, Glob]
---

## Path Resolution

`<skill-root>` is the directory containing this `SKILL.md`. Resolve `scripts/...` and `references/...` relative to it (e.g. `<skill-root>/references/examples.md`), not the caller's current working directory.

# Commit in Meaningful Units

## Scope and Invocation

- Runs only via `/commit`. Never commit automatically or as part of another task.
- Creates local commits only — no `git push`, no pull requests (use the `create-pr` skill), no merge/rebase.

## Ask Discipline

First inspect the diff and infer the safest action from the rules below; form a tentative plan before asking. Ask the user only when proceeding would risk data loss, create an irreversible or policy-ambiguous commit, or require choosing between groupings the diff cannot resolve. When you do ask, lead with your recommended option and the trade-off — never an open-ended question when a bounded recommendation is possible.

## Core Principle: One Logical Change Per Commit

Each commit is exactly one meaningful unit: one clear purpose, independently revertible, describable in a single specific subject with no "and". Bundling unrelated changes makes reverts dangerous (reverting one fix undoes an unrelated feature), review noisy, and `git bisect` useless. For good/bad groupings and common scenarios, see [examples.md](references/examples.md).

## Context
- Status: !`git status --short`
- Branch: !`git branch --show-current`
- Recent: !`git log --oneline -10`
- Unstaged: !`git diff --stat`
- Staged: !`git diff --cached --stat`

Cached snapshots may be stale — always re-verify with live commands before acting.

## Message Format

Allowed forms: `type(scope): subject` or `type: subject`.

**Types:** `feat` (new feature), `fix` (bug fix), `docs`, `style` (code style), `refactor`, `perf`, `test`, `chore` (maintenance), `build` (build system), `ci`.

**Rules:**
- Subject ≤50 characters, no trailing period.
- English: imperative mood, lowercase start (`fix bug`, not `Fix bug`). Japanese: である調, カタカナ for tech terms.
- `scope` is optional and names exactly one area. Never use multiple scopes (`feat(mysql,cli): ...`) — split into separate commits first, or omit scope (`type: subject`) when the change is one inseparable unit.
- Treat `and` in an English subject as a red flag: split, or rewrite to a single purpose.

**Language selection:**
- `--english`: English description. `--japanese`: English type/scope with a Japanese description.
- Neither flag: match the dominant language of recent commit subjects (`git log --format='%s' -10`). If recent commits are mixed or unclear, pick the safer default from the user's current language and repository context; ask only when those signals conflict.

Examples: `feat(auth): add OAuth2 login` · `fix(api): handle null user responses` · `feat: centralize request validation` · `feat(auth): OAuth2ログインを追加` · `fix(api): ユーザーのnull処理を修正`

## Process

1. **Analyze**: `git diff` — identify every logical unit before committing anything. If changes are mixed, plan separate commits. A subject that wants multiple scopes or `and` is a signal to split first. If grouping stays ambiguous after self-analysis, see **Identifying Meaningful Units**.
2. **Choose language** (see Language selection).
3. **For each logical unit, separately:**
   - Stage only related files: `git add <specific-files>`, or use **Patch-Based Partial Staging** for partial changes within a file.
   - Verify: `git diff --cached` — ensure exactly one logical change is staged. If staging is wrong, stop and ask (see **Prohibited Commands**).
   - Draft the subject and run **Subject Sanity Checks**.
   - Commit: `git commit -m "<type>(<scope>): subject"` (or `git commit -m "<type>: subject"`), then confirm with `git log --oneline -1`.
4. Repeat until all changes are committed.

**With `--branch`:** before staging (step 3), derive a descriptive branch name from the primary change (`<type>/<descriptive-name>`, no abbreviations) and create it with `git switch -c <name>`. Branch creation is mandatory when `--branch` is set. Base defaults to the current branch; with `--base=<branch>`, run `git switch <base>` first. Examples: `feature/add-oauth-support`, `fix/handle-null-values`.

### Subject Sanity Checks

Before committing, validate the drafted subject mechanically (run each as one complete shell command — do not pass `printf` and `wc` as separate tool arguments):

```bash
printf '%s' 'feat: centralize request validation' | wc -c
printf '%s\n' 'feat: centralize request validation' | rg -n '\band\b'
```

If `wc -c` exceeds 50, rewrite before committing. If `rg` matches `and` in an English subject, treat it as a forced reconsideration: split into separate commits first; if the change is truly inseparable, rephrase to a single purpose without `and`.

### Patch-Based Partial Staging

When one file holds multiple logical changes, stage hunks selectively via an editable patch. See [examples.md](references/examples.md#patch-based-partial-staging) for the full procedure.

### Prohibited Commands While Splitting

To prevent accidental data loss, never run these while preparing partial commits — pause and ask the user for explicit direction instead:
- `git restore ...`, `git reset ...`, `git checkout -- ...` (or `git checkout -f`), `git switch --discard-changes ...`, `git clean ...`

## Identifying Meaningful Units

Ask of each candidate unit: Can it stand alone if reverted? Does it have one purpose (one sentence, no "and")? Are all parts necessary to each other? Would its scope be clear to a future reader?

Scope decision order:
1. If the change spans multiple areas, try to split it into separate commits first.
2. If it is one inseparable change, use `type: subject`.
3. Use `type(scope): subject` only when the unit is clearly centered on one area.

When grouping is uncertain, decide yourself first: list the changed files/hunks by purpose, apply the questions above, prefer separate commits when independent revertibility is clear, and prefer one unscoped commit only when splitting would break a single logical change. Ask only if two or more groupings remain plausible — and then present the options with your recommendation first (which options are under consideration, how the choice affects commit count and revertibility, why yours is safest). Use AskUserQuestionTool if available, batching multiple decisions into its `questions` array; otherwise ask in one message using `Q1`/`Q2` labels and request `QID: <answer>` replies (allow `QID: OTHER(<detail>)`). See [examples.md](references/examples.md#when-uncertain-about-grouping--example-prompt).

## Error Handling

- **@ symbols**: wrap code/paths containing `@` in backticks (`` `@import` ``, `` `path/@file` ``) so GitHub does not turn them into user mentions.
- **Hook failures**: read the error, show it to the user in full, and ask how to proceed. Never bypass hooks.
- **Signing failures** (1Password/GPG/SSH): show the exact error and stop the workflow. Do NOT change signing config or bypass signing (no `git config commit.gpgsign false`, no `--no-gpg-sign` / `-c commit.gpgsign=false`). Wait for user instruction.

## Anti-Patterns

Red flags that signal bundled changes: `and` in an English subject; vague messages like "various fixes"; comma-separated scopes; staging all files without reviewing each; a "cleanup" commit that hides functional changes; bundling a hotfix with a feature because "it's one line". When in doubt, make separate commits — you can always squash later.
