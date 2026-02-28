---
name: commit
description: Creates meaningful git commits by analyzing changes and committing in logical units. Use when the user wants to commit changes to git, requests commit creation, or asks to save changes to version control. Supports --japanese flag for Japanese commit messages and --branch flag to create a new branch before committing.
allowed-tools: [Bash, Read, Grep, Glob]
---

# Commit in Meaningful Units

## Not in Scope

- `git push` — this skill creates local commits only.
- Creating pull requests — use the `create-pr` skill.
- Merging or rebasing branches.

## Invocation Guard

This skill runs only via `/commit`. Never create commits automatically or as part of another task.

## Core Principle: One Logical Change Per Commit

Every commit represents exactly one meaningful unit of change. Bundling unrelated changes makes reverts dangerous (reverting one fix undoes an unrelated feature), makes code review noisy, and makes `git bisect` useless. A meaningful unit:
- Has one clear purpose
- Can be reverted independently without breaking other functionality
- Can be described with a single, specific commit message (no "and")

For examples of good/bad groupings and common scenarios, see [examples.md](references/examples.md).

## Context
- Status: !`git status --short`
- Branch: !`git branch --show-current`
- Recent: !`git log --oneline -10`
- Unstaged: !`git diff --stat`
- Staged: !`git diff --cached --stat`

Always verify actual git state with live commands — cached snapshots from skill context may be stale.

## Language Support

**--japanese**: Creates commit messages with English types but Japanese descriptions:
- Format: `<type>(<scope>): <日本語の説明>`
- Examples:
  - `feat(auth): OAuth2ログインを追加`
  - `fix(api): ユーザーエンドポイントのnull処理を修正`
  - `refactor(utils): バリデーションロジックを抽出`
- Use である調, keep under 50 chars, use カタカナ for tech terms

## Branch Support

**--branch**: Creates a new branch before committing:
- When `--branch` is specified, branch creation is mandatory — skipping it defeats the purpose of the flag
- Branch name is automatically determined from the primary change in the diff
- Creates branch using `git switch -c <branch-name>`
- Branch names use descriptive names without abbreviations
- Default base: current branch
- Use `--base=<branch>` to specify a different base branch
- Examples:
  - `/commit --branch` → Auto-generates name like `feature/add-oauth-support`
  - `/commit --branch --base=main` → Create from main branch
  - `/commit --branch --base=develop` → Create from develop branch

## Commit Format

**Types:**
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

**Rules:**
- Max 50 characters for subject line
- Imperative mood (English) / である調 (Japanese)
- Start English subject with lowercase (e.g., `fix bug`, not `Fix bug`)
- No period at end
- Format: `type(scope): subject`

## Process

### Standard Process
1. **Analyze first**: `git diff` — identify every logical unit before making any commits
   - Group changes by their purpose and plan separate commits for each unit
   - If changes are mixed, split them before proceeding
   - If uncertain about grouping: use AskUserQuestionTool
2. **Check state**: `git status`
3. **For EACH logical unit separately**:
   - **Stage ONLY related files**:
     - For whole-file commits: `git add <specific-files>`
     - For partial staging within a file: follow **Patch-Based Partial Staging**
   - **Verify staged changes**: `git diff --cached` — ensure only one logical change is staged
   - **If staging is wrong**: stop and ask user before proceeding (see Prohibited Commands)
   - **Commit**: `git commit -m "type(scope): description"`
   - **Confirm**: `git log --oneline -1`
4. **Repeat for next logical unit** until all changes are committed

### With --branch Option
1. **Analyze first**: `git diff` — identify every logical unit and determine primary change
2. **Check state**: `git status`
3. **Determine branch name**: Analyze diff to generate descriptive branch name based on primary change
   - Format: `<type>/<descriptive-name>`
   - Examples: `feature/add-oauth-support`, `fix/handle-null-values`, `refactor/extract-validation`
4. **Switch to base branch** (if `--base` specified): `git switch <base-branch>`
5. **Create branch**: `git switch -c <branch-name>`
6. **For EACH logical unit separately**:
   - **Stage ONLY related files**:
     - For whole-file commits: `git add <specific-files>`
     - For partial staging within a file: follow **Patch-Based Partial Staging**
   - **Verify staged changes**: `git diff --cached` — ensure only one logical change is staged
   - **If staging is wrong**: stop and ask user before proceeding (see Prohibited Commands)
   - **Commit**: `git commit -m "type(scope): description"`
   - **Confirm**: `git log --oneline -1`
7. **Repeat for next logical unit** until all changes are committed

### Patch-Based Partial Staging

When a file contains multiple logical changes, use the patch-based approach. See [examples.md](references/examples.md#patch-based-partial-staging) for the full procedure.

### Prohibited Commands During Partial Commit Preparation

To prevent accidental data loss, the following are NOT allowed while splitting changes into logical commits:
- Any `git restore ...` command
- Any `git reset ...` command
- Any `git checkout -- ...` command (or `git checkout -f`)
- Any `git switch --discard-changes ...` command
- Any `git clean ...` command (e.g. `git clean -fd`, `git clean -fdx`)

If these commands seem necessary, pause and ask the user for explicit direction instead of executing them.

## Identifying Meaningful Units

### Ask These Questions:
1. **Can this change stand alone?** If reverted, would the codebase still make sense?
2. **Does it have a single purpose?** Can you describe it in one sentence without "and"?
3. **Are all parts necessary for each other?** Would removing any part break the change?
4. **Would a future developer understand it?** Is the change's scope immediately clear?

### When Uncertain About Grouping

**When uncertain about grouping**, present the changes and options via AskUserQuestionTool. Include in the question text: (1) which grouping options are under consideration, (2) how the decision affects commit count and independent revertibility. See [examples.md](references/examples.md#when-uncertain-about-grouping--example-prompt) for an example prompt.

### Common Scenarios

For scenarios requiring separate commits (refactoring + feature, bug fix + test, etc.), see [examples.md](references/examples.md#common-scenarios-requiring-separate-commits).

## Character Count
```bash
# Check length
echo -n "feat(auth): add OAuth2 support" | wc -c
```

## Handling @ Symbols
When commit messages contain @ symbols:
- Wrap code/paths in backticks to prevent GitHub mentions: `@import` or `path/@file`
- This prevents unintended user notifications

## Hook Errors
If commit-msg hook fails:
- Read error carefully
- Show full error to user
- Ask how to proceed
- Don't bypass hooks

## Signing Errors (1Password/GPG/SSH)
If commit signing fails (for example with 1Password or other signing agents):
- Read and show the exact error to the user
- STOP the commit workflow and ask the user how to proceed
- Do NOT modify git signing config to force commit success
- Do NOT run `git config` changes for signing bypass (e.g. `git config commit.gpgsign false`, `git config --global commit.gpgsign false`)
- Do NOT run bypass options such as `--no-gpg-sign` or `-c commit.gpgsign=false`
- Wait for user instruction after reporting the failure

## Anti-Patterns

Red flags that indicate multiple logical changes are bundled:
- Commit message contains "and" (except in detailed descriptions)
- Using vague messages like "various fixes" or "multiple improvements"
- Staging all changed files without reviewing each one
- Making a "cleanup" commit that includes functional changes
- Bundling a hotfix with a feature because "it's just one line"

## Final Reminders
- When in doubt, make separate commits — you can always squash later
- For Japanese commits, ensure UTF-8 support in your environment
