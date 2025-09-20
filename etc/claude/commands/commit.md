---
allowed-tools: [Bash, Read, Grep, Glob, TodoWrite]
argument-hint: --japanese | --branch
description: Create meaningful git commits by analyzing changes and committing in logical units
---

# Commit in Meaningful Units

## 🚨 FUNDAMENTAL PRINCIPLE: One Logical Change Per Commit

**Every commit MUST represent exactly ONE meaningful unit of change.** This is the most important rule of good commit hygiene. A meaningful unit is a single, coherent change that:
- Has ONE clear purpose
- Could be reverted independently without breaking other functionality
- Makes sense in isolation from other changes
- Can be described with a single, specific commit message

### ❌ NEVER Bundle Unrelated Changes

**Common violations to avoid:**
- Fixing a bug AND adding a new feature
- Refactoring code AND changing behavior
- Updating documentation AND modifying implementation
- Fixing multiple unrelated bugs in one commit
- Making style changes alongside functional changes

### ✅ Examples of Meaningful Units

**Good (separate commits):**
- `fix(auth): handle null user sessions`
- `refactor(auth): extract session validation logic`
- `feat(auth): add remember me option`

**Bad (bundled together):**
- `fix(auth): handle null sessions and add remember me option and refactor validation`

## Context
- Status: !`git status --short`
- Branch: !`git branch --show-current`
- Recent: !`git log --oneline -10`
- Unstaged: !`git diff --stat`
- Staged: !`git diff --cached --stat`

**⚠️ CRITICAL: Always verify actual git state with live commands.**

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
- Creates feature branch using `git switch -c <branch-name>`
- Branch names should use descriptive names without abbreviations
- Always create from current branch or main/master
- Examples:
  - `--branch feature/add-oauth-support`
  - `--branch fix/handle-null-values`
  - `--branch refactor/extract-validation-logic`

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
- No period at end
- Format: `type(scope): subject`

## Process

### Standard Process
1. **🔍 ANALYZE FIRST**: `git diff` - identify EVERY logical unit
   - Review ALL changes before ANY commits
   - Group changes by their purpose
   - Plan separate commits for each unit
   - NEVER proceed if changes are mixed
   - **If uncertain about grouping**: Use human-in-the-loop tools (or ask directly if unavailable)
2. **Check state**: `git status`
3. **For EACH logical unit separately**:
   - **Stage ONLY related files**: `git add <specific-files>` or `git add -p`
   - **Verify staged changes**: `git diff --cached` - ensure ONLY one logical change
   - **Commit**: `git commit -m "type(scope): description"`
   - **Confirm**: `git log --oneline -1`
4. **Repeat for next logical unit** until all changes are committed

### With --branch Option
1. **🔍 ANALYZE FIRST**: `git diff` - identify EVERY logical unit
2. **Check state**: `git status`
3. **Create branch**: `git switch -c <branch-name>` (based on primary change)
4. **For EACH logical unit separately**:
   - **Stage ONLY related files**: `git add <specific-files>` or `git add -p`
   - **Verify staged changes**: `git diff --cached` - ensure ONLY one logical change
   - **Commit**: `git commit -m "type(scope): description"`
   - **Confirm**: `git log --oneline -1`
5. **Repeat for next logical unit** until all changes are committed

### Interactive Staging for Mixed Files

When a single file contains multiple logical changes, use `git add -p`:
- Review each hunk carefully
- Stage ONLY hunks related to the current logical unit
- Leave unrelated changes for separate commits

## Identifying Meaningful Units

### Ask These Questions:
1. **Can this change stand alone?** If reverted, would the codebase still make sense?
2. **Does it have a single purpose?** Can you describe it in one sentence without "and"?
3. **Are all parts necessary for each other?** Would removing any part break the change?
4. **Would a future developer understand it?** Is the change's scope immediately clear?

### When Uncertain About Grouping

**If you have LOW CONFIDENCE about whether changes belong together:**

1. **FIRST: Use human-in-the-loop tools** (if available)
   - Present the changes you're unsure about
   - Explain your reasoning for potential groupings
   - Let the tool guide the decision

2. **IF human-in-the-loop tools are unavailable:**
   - **STOP and ASK** the user directly
   - Clearly present the ambiguous changes
   - Provide grouping options with reasoning
   - Wait for user confirmation before proceeding

**Common uncertainty triggers:**
- Changes touch related but distinct features
- Refactoring mixed with small behavior tweaks
- Multiple files changed for what might be one feature
- Dependencies between changes are unclear
- Changes could be seen as either one large feature or multiple small ones

**Example prompt when uncertain:**
```
I see changes to both authentication and user profile code. I'm unsure if these should be:
1. One commit (if profile changes depend on auth changes)
2. Two commits (if they're independent improvements)

The changes are:
- auth.js: Added session timeout handling
- profile.js: Added avatar upload validation

How would you like me to group these changes?
```

### Common Scenarios Requiring Separate Commits:

**Refactoring + Feature:**
- COMMIT 1: Refactor existing code (no behavior change)
- COMMIT 2: Add new feature using refactored structure

**Bug Fix + Test:**
- COMMIT 1: Add failing test that demonstrates the bug
- COMMIT 2: Fix the bug (test now passes)

**Multiple Bug Fixes:**
- COMMIT 1: Fix null pointer in user service
- COMMIT 2: Fix race condition in cache manager
- COMMIT 3: Fix memory leak in data processor

**Style + Logic Changes:**
- COMMIT 1: Fix business logic error
- COMMIT 2: Format/lint the affected files

## Best Practices

### 🔴 NON-NEGOTIABLE RULES:
1. **ONE logical change per commit** - This is absolute
2. **NEVER mix different types of changes** - No exceptions
3. **Each commit must be independently valid** - Code works after every commit
4. **Commit message must describe ONE thing** - If you need "and", make separate commits

### Additional Guidelines:
- Use clear, specific messages
- Use `git add -p` for surgical precision when needed
- If unsure, err on the side of MORE commits, not fewer

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

## ⚠️ Common Anti-Patterns to Avoid

**Red flags that indicate you're violating the meaningful units principle:**
- Commit message contains "and" (except in detailed descriptions)
- Using vague messages like "various fixes" or "multiple improvements"
- Staging all changed files without reviewing each one
- Making a "cleanup" commit that includes functional changes
- Bundling a hotfix with a feature because "it's just one line"

## Final Reminders
- Always verify actual git state with live commands
- For Japanese commits, ensure UTF-8 support in your environment
- **When in doubt, make separate commits** - you can always squash later
