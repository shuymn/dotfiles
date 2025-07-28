---
allowed-tools: [Bash, Read, Grep, Glob, TodoWrite]
description: Create meaningful git commits by analyzing changes and committing in logical units
---

# Commit in Meaningful Units

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

1. **Check state**: `git status`
2. **Review changes**: `git diff`
3. **Stage logical unit**: `git add <files>` or `git add -p`
4. **Verify**: `git diff --cached`
5. **Commit**: `git commit -m "type(scope): description"`
6. **Confirm**: `git log --oneline -1`

## Best Practices
- One logical change per commit
- Each commit should leave code working
- Don't mix unrelated changes
- Use clear, specific messages
- Stage only related files

## Character Count
```bash
# Check length
echo -n "feat(auth): add OAuth2 support" | wc -c
```

## Hook Errors
If commit-msg hook fails:
- Read error carefully
- Show full error to user
- Ask how to proceed
- Don't bypass hooks

## Important
- Always verify with actual git commands
- Focus on clarity and maintainability
- For Japanese, ensure UTF-8 support
