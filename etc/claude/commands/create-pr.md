---
allowed-tools: [Bash, Read, Grep, Glob, TodoWrite, mcp__github__create_pull_request, mcp__github__get_me]
description: Review committed changes and create a pull request on GitHub (English by default, Japanese with --japanese)
---

# Create Pull Request on GitHub from Committed Changes

## Context

### Git Information
- Current branch: `git branch --show-current`
- Remote branches: `git branch -r`
- Default branch: `git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'`
- Repository root: `git rev-parse --show-toplevel`
- Unpushed commits: `git log origin/$(git branch --show-current)..HEAD --oneline 2>/dev/null || echo "Branch not pushed yet"`
- Push status: `git status -sb | head -1`

### Committed Changes Only
- Commits different from default branch: `git log $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD --oneline`
- Number of commits ahead: `git rev-list --count $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD`
- Files changed in commits: `git diff --name-status $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD`
- Lines added/removed: `git diff --shortstat $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD`
- Full diff: `git diff $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD`

### Detailed Commit History
- Commit messages with body: `git log $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD --format="### %s%n%n%b%n"`
- Commit authors: `git log $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD --format="%an <%ae>" | sort | uniq`

### PR Templates
- GitHub template: `cat .github/pull_request_template.md 2>/dev/null || echo "No GitHub template"`
- Alternative template: `cat .github/PULL_REQUEST_TEMPLATE.md 2>/dev/null || echo ""`

### Project Information
- README: `cat README.md 2>/dev/null | head -50 || echo "No README"`

## Language Support

**Default**: English  
**--japanese**: Creates PR in Japanese

## Your Task

Based on the above context (focusing ONLY on committed changes), create and submit a pull request on GitHub:

### 1. Analyze Committed Changes
- Review all commits between current branch and default branch
- Understand intent from commit messages
- Identify types and scope of changes
- Check for breaking changes
- Classify commits (feature, fix, refactor, docs, etc.)

### 2. Use PR Template If Exists
- Follow template format strictly
- Fill sections based on committed changes only
- Delete empty sections
- Maintain checklist format (- [ ])

### 3. Standard Format If No Template

**English (Default):**
```markdown
## Summary
[2-3 sentences explaining purpose and background of commits]

## Changes
- [Major change from commits]
- [Major change from commits]

## Motivation
[Why these commits were necessary]

## Technical Details
[Implementation approach from commits]

## Impact
- Affected features: [Features affected by commits]
- Affected files: [Major files changed]
- Breaking changes: [Yes/No]

## Testing
1. [Test step 1]
2. [Test step 2]

## Checklist
- [ ] Code works as expected
- [ ] Tests have been added/updated
- [ ] Documentation has been updated (if necessary)
- [ ] Linter and formatter have been run
- [ ] Breaking changes are clearly documented

## Additional Notes
[Additional information for reviewers]
```

**Japanese (--japanese):**
```markdown
## 概要
[コミットの目的と背景を2-3文で説明]

## 変更内容
- [コミットからの主な変更]
- [コミットからの主な変更]

## 変更理由
[これらのコミットが必要だった理由]

## 技術的詳細
[コミットからの実装アプローチ]

## 影響範囲
- 影響を受ける機能：[コミットにより影響を受ける機能]
- 影響を受けるファイル：[変更された主要ファイル]
- 破壊的変更：[あり/なし]

## テスト方法
1. [テスト手順1]
2. [テスト手順2]

## チェックリスト
- [ ] コードは正常に動作することを確認した
- [ ] 適切なテストを追加/更新した
- [ ] ドキュメントを更新した（必要な場合）
- [ ] LintやFormatterを実行した
- [ ] 破壊的変更がある場合は明記した

## その他
[レビュアーへの追加情報]
```

### 4. Writing Guidelines

**English:**
- Use clear, concise English
- Keep code references and file paths as-is
- Be direct and professional
- Wrap @ symbols in code/paths with backticks to prevent mentions: `@import`, `path/@file`

**Japanese:**
- Use appropriate technical Japanese
- Keep English proper nouns (libraries, functions) as-is
- Use clear Japanese without honorifics
- Use である調 for professional tone

### 5. Execution Steps

0. **Ensure changes are pushed**:
   ```bash
   git push -u origin [current branch name]
   ```

1. **Prepare PR content**:
   - Generate appropriate title summarizing commits
   - Create PR body following template or standard format

2. **Create pull request**:
   ```
   mcp__github__create_pull_request:
   - title: [Generated title in selected language]
   - body: [Generated body in selected language]
   - head: [Current branch]
   - base: [Default branch]
   ```

3. **After creation**:
   - Provide PR URL
   - Confirm success
   - Explain any errors clearly

## Important Notes
- ONLY analyze committed changes (ignore uncommitted work)
- Notify if no commits exist between branches
- Focus on what was committed, not work in progress
- Be concise, avoid redundancy across sections
- Actually CREATE the PR using mcp__github__create_pull_request
- ULTRATHINK. DO YOUR BEST.
