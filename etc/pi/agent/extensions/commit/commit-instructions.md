# Commit in Meaningful Units

You are running the /commit extension. Create local git commits only.

## Not in Scope

- Do not run git push.
- Do not create pull requests.
- Do not merge or rebase branches.

## Core Principle: One Logical Change Per Commit

Every commit represents exactly one meaningful unit of change. A meaningful unit:

- Has one clear purpose.
- Can be reverted independently without breaking unrelated work.
- Can be described with a single, specific commit message without "and".

## Language Support

The extension asks for language interactively. The selected options shown in the prompt are authoritative and mutually exclusive.

**English**: Create commit messages with English types and English descriptions:

- Format: `<type>(<scope>): <english description>` or `<type>: <english description>`
- Use imperative mood, keep under 50 chars, start the subject with lowercase.

**Japanese**: Create commit messages with English types and optional scope plus Japanese descriptions:

- Format: `<type>(<scope>): <日本語の説明>` or `<type>: <日本語の説明>`
- Use である調, keep under 50 chars, use カタカナ for tech terms.

**Auto**:

- First inspect your own recent commit subjects using your configured `user.email` (or `user.name` if no email is configured), for example `git log --author="$(git config user.email)" --format='%s' -10`.
- Match the dominant description language in your own recent commits.
- If your own recent commits are unavailable or empty in this repository, inspect all recent commit subjects with `git log --format='%s' -10` as a fallback.
- Match the dominant description language in the fallback history.
- If the applicable recent commits do not show a clear preference, ask the user before committing.

## Branch Support

The extension asks interactively whether to create a branch and, when needed, asks for a base branch from the branch list.

When branch creation is selected:

- Branch creation is mandatory.
- Determine the new branch name from the primary change in the diff.
- Switch to the selected base branch first.
- Use `git switch -c <branch-name>`.
- Branch names use descriptive names without abbreviations.
- Branch name format: `<type>/<descriptive-name>` such as `feat/add-oauth-support`, `fix/handle-null-values`, `refactor/extract-validation`.

## Commit Format

Types:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style
- `refactor`: Refactoring
- `perf`: Performance
- `test`: Tests
- `chore`: Maintenance
- `build`: Build system
- `ci`: CI changes

Rules:

- Max 50 characters for subject line.
- Imperative mood for English / である調 for Japanese.
- Start English subjects with lowercase.
- No period at end.
- Treat English subject `and` as a red flag; reconsider split or wording.
- Allowed formats: `type(scope): subject` and `type: subject`.
- `scope` is optional and must name exactly one area when present.
- Never use multiple scopes such as `feat(mysql,cli,testkit): ...`.
- If a change appears to need multiple scopes, first try splitting it into separate commits.
- If splitting would break one logical change, omit scope and use `type: subject`.

## Required Process

1. Analyze first with `git diff` and identify every logical unit before making commits.
    - Group changes by purpose and plan separate commits for each unit.
    - If changes are mixed, split them before proceeding.
    - If the message seems to need multiple scopes, treat that as a signal to split commits first.
    - If uncertain about grouping, ask the user.
2. Check state with `git status`.
3. Choose commit language according to the interactive option or recent history.
4. If branch creation is selected:
    - Determine the branch name from the primary change.
    - Run `git switch <selected-base-branch>`.
    - Run `git switch -c <branch-name>` before committing.
5. For each logical unit separately:
    - Stage only related files.
    - For whole-file commits: `git add <specific-files>`.
    - For partial staging within a file: use the patch-based partial staging process below.
    - Verify staged changes with `git diff --cached` and ensure only one logical change is staged.
    - If staging is wrong, stop and ask the user before proceeding.
    - Draft the subject and run subject sanity checks.
    - Commit with `git commit -m "<subject>"`.
    - Confirm with `git log --oneline -1`.
6. Repeat until all intended changes are committed.

## Patch-Based Partial Staging

When a file contains multiple logical changes:

1. Export the full diff for target files: `git diff -- <target-file> > /tmp/partial-stage.patch`.
2. Back it up: `cp /tmp/partial-stage.patch /tmp/partial-stage.full.patch`.
3. Edit `/tmp/partial-stage.patch` and remove hunks unrelated to the current logical unit.
4. Validate: `git apply --check --cached /tmp/partial-stage.patch`.
5. Apply to index only: `git apply --cached /tmp/partial-stage.patch`.
6. Verify with `git diff --cached` and `git diff`.
7. If check/apply fails, stop and ask the user how to proceed.

## Subject Sanity Checks

Before `git commit`, validate the drafted subject mechanically:

```bash
printf '%s' 'feat: centralize request validation' | wc -c
printf '%s\n' 'feat: centralize request validation' | rg -n '\band\b'
```

- If `wc -c` exceeds 50, rewrite before committing.
- If `rg` matches `and` in an English subject, reconsider split or wording.
- Run each check as a complete shell command.

## Prohibited Commands During Partial Commit Preparation

Do not use these commands while splitting changes into logical commits:

- Any `git restore ...` command.
- Any `git reset ...` command.
- Any `git checkout -- ...` command or `git checkout -f`.
- Any `git switch --discard-changes ...` command.
- Any `git clean ...` command.

If these commands seem necessary, pause and ask the user for explicit direction.

## Identifying Meaningful Units

Ask:

1. Can this change stand alone?
2. Does it have a single purpose?
3. Are all parts necessary for each other?
4. Would a future developer understand it?

Scope decision order:

1. If the change spans multiple areas, try to split it first.
2. If it still forms one inseparable logical change, use `type: subject`.
3. Use `type(scope): subject` only when centered on one area.

Common separate-commit scenarios:

- Refactoring plus feature: separate refactor and feature commits.
- Bug fix plus test: separate failing test and fix when practical.
- Multiple bug fixes: one commit per bug.
- Style plus logic: separate formatting/linting from behavior.
- Cross-cutting but inseparable: one commit without scope.

## Error Handling

- If a commit hook fails, read the error, show it to the user, ask how to proceed, and do not bypass hooks.
- If signing fails (1Password/GPG/SSH), show the exact error, stop, and ask how to proceed.
- Do not change git signing config, use `--no-gpg-sign`, or use `-c commit.gpgsign=false` unless the user explicitly instructs after seeing the failure.

## Final Reminders

- Verify actual git state with live commands; any provided context may be stale.
- Never stage all changed files without reviewing each one.
- When in doubt, make separate commits. The user can squash later.
