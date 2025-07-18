---
allowed-tools: Bash(git branch:*), Bash(git diff:*), Bash(git log:*), Bash(git remote:*), Bash(git rev-parse:*), Bash(cat:*), Bash(find:*), ReadFile, mcp__github__create_pull_request, mcp__github__get_me
description: Review committed changes and create a Japanese pull request on GitHub
---

# Create Japanese Pull Request on GitHub from Committed Changes

## Context

### Git Information
- Current branch: !`git branch --show-current`
- Remote branches: !`git branch -r`
- Default branch: !`git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'`
- Repository root: !`git rev-parse --show-toplevel`
- Unpushed commits: !`git log origin/$(git branch --show-current)..HEAD --oneline 2>/dev/null || echo "Branch not pushed yet"`
- Push status: !`git status -sb | head -1`

### Committed Changes Only
- Commits different from default branch: !`git log $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD --oneline`
- Number of commits ahead: !`git rev-list --count $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD`
- Files changed in commits: !`git diff --name-status $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD`
- Number of files changed: !`git diff --name-only $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD | wc -l`
- Lines added/removed: !`git diff --shortstat $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD`
- Full diff of committed changes: !`git diff $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD`

### Detailed Commit History
- Commit messages with body: !`git log $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD --format="### %s%n%n%b%n"`
- Commit authors: !`git log $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD --format="%an <%ae>" | sort | uniq`
- First commit in branch: !`git log $(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')..HEAD --reverse --oneline | head -1`
- Last commit in branch: !`git log -1 --oneline`

### PR Templates
- GitHub template: !`cat .github/pull_request_template.md 2>/dev/null || echo "No GitHub template"`
- Alternative template: !`cat .github/PULL_REQUEST_TEMPLATE.md 2>/dev/null || echo ""`

### Project Information
- README: !`cat README.md 2>/dev/null | head -50 || echo "No README"`
- Project structure: !`find . -type f -name "*.md" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" | grep -E "(README|CONTRIBUTING|CHANGELOG)" | head -10`

## Your task

Based on the above context (focusing ONLY on committed changes, ignoring any uncommitted local changes), create and submit a pull request on GitHub in Japanese following these steps:

### 1. Analyze Committed Changes
- Review all commits between current branch and default branch
- Understand the intent from commit messages
- Identify types and scope of changes from committed files only
- Check for breaking changes in commits
- Classify commits as: new feature, bug fix, refactoring, documentation update, etc.

### 2. Use PR Template
- If a template exists, strictly follow its format
- Fill in each section in Japanese based on committed changes only
- Headings with no content should be deleted
- Maintain checklist format (- [ ])

### 3. If No Template Exists, Use This Standard Format

```markdown
## 概要
[Write 2-3 sentences explaining the purpose and background of commits in Japanese]

## 変更内容
- [Major change from commits in Japanese]
- [Major change from commits in Japanese]
- [Major change from commits in Japanese]

## 変更理由
[Explain why these commits were necessary in Japanese]

## 技術的詳細
[Explain implementation approach from commits in Japanese]

## 影響範囲
- 影響を受ける機能：[Feature names affected by commits in Japanese]
- 影響を受けるファイル：[Major files changed in commits]
- 破壊的変更：[あり/なし]

## テスト方法
1. [Test step 1 in Japanese]
2. [Test step 2 in Japanese]
3. [Test step 3 in Japanese]

## チェックリスト
- [ ] コードは正常に動作することを確認した
- [ ] 適切なテストを追加/更新した
- [ ] ドキュメントを更新した（必要な場合）
- [ ] LintやFormatterを実行した
- [ ] 破壊的変更がある場合は明記した

## その他
[Additional information for reviewers in Japanese]
```

### 4. Writing Guidelines
- Base everything on committed changes only
- Ignore any uncommitted work in progress
- Use appropriate Japanese translations for technical terms
- Keep English proper nouns (library names, function names) as-is
- Use clear, concise Japanese without honorifics
- Properly format code blocks and inline code with markdown

### 5. Final Output
Execute the following steps to create the pull request:

0. **Ensure changes are pushed**:
   - Check if there are unpushed commits
   - If branch hasn't been pushed yet, push it first:
     ```
     git push -u origin [current branch name]
     ```
   - Confirm remote branch exists before creating PR
 
1. **Prepare PR content**:
   - Generate an appropriate Japanese title that summarizes the commits
   - Create the PR body following the template or standard format above

2. **Create the pull request using GitHub MCP**:
   ```
   Use mcp__github__create_pull_request with:
   - title: [Generated Japanese title based on commits]
   - body: [Generated Japanese PR body from above]
   - head: [Current branch name from git context]
   - base: [Default branch name from git context]
   ```

3. **After creation**:
   - Provide the PR URL to the user
   - Confirm successful creation
   - If any errors occur, explain them clearly

## Important Notes
- ONLY analyze committed changes (ignore uncommitted local changes)
- If no commits exist between current branch and default branch, notify user
- All PR content (title and body) must be written in Japanese
- Focus on what was actually committed, not what might be in progress
- Do not describe the same content across sections or pad your writing by exaggerating achievements. Be simple.
- Actually CREATE the pull request using mcp__github__create_pull_request - don't just generate the content
- ULTRATHINK. DO YOUR BEST.
