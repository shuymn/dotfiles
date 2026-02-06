---
name: create-pr
description: Review committed changes and create a pull request on GitHub. Use when the user wants to create a PR, requests pull request creation, or asks to open changes for review. Supports --japanese flag for Japanese PR descriptions, --base flag to specify target branch, and --update flag to update existing PR. Works with GitHub repositories using the github MCP server.
allowed-tools: [Bash, Read, Grep, Glob, TodoWrite]
---

# Create Pull Request on GitHub from Committed Changes

## Context

### Git Information
- Current branch: `git branch --show-current`
- Remote branches: `git branch -r`
- Default branch: `git symbolic-ref --short refs/remotes/origin/HEAD | sed 's@^origin/@@'`
- Repository root: `git rev-parse --show-toplevel`
- Unpushed commits: `git log origin/$(git branch --show-current)..HEAD --oneline 2>/dev/null || echo "Branch not pushed yet"`
- Push status: `git status -sb | head -1`

### Committed Changes Only
**Note**: Replace `origin/HEAD` with `origin/<base-branch>` if `--base=<branch>` is specified

- Commits different from base branch: `git log origin/HEAD..HEAD --oneline`
- Number of commits ahead: `git rev-list --count origin/HEAD..HEAD`
- Files changed in commits: `git diff --name-status origin/HEAD..HEAD`
- Lines added/removed: `git diff --shortstat origin/HEAD..HEAD`
- Full diff: `git diff origin/HEAD..HEAD`

### Detailed Commit History
**Note**: Replace `origin/HEAD` with `origin/<base-branch>` if `--base=<branch>` is specified

- Commit messages with body: `git log origin/HEAD..HEAD --format="### %s%n%n%b%n"`
- Commit authors: `git log origin/HEAD..HEAD --format="%an <%ae>" | sort | uniq`

### PR Templates
- GitHub template: `cat .github/pull_request_template.md 2>/dev/null || echo "No GitHub template"`
- Alternative template: `cat .github/PULL_REQUEST_TEMPLATE.md 2>/dev/null || echo ""`

### Project Information
- README: `cat README.md 2>/dev/null | head -50 || echo "No README"`

## Language Support

**Default**: English
**--japanese**: Creates PR in Japanese

## Base Branch Support

**Default**: Repository's default branch (usually `main` or `master`)
**--base=<branch>**: Specify target branch for the pull request

- Use `--base=<branch>` to create PR against a specific branch
- Default behavior: Uses repository default branch from `git symbolic-ref --short refs/remotes/origin/HEAD`
- Examples:
  - `/create-pr` → Creates PR to default branch
  - `/create-pr --base=develop` → Creates PR to develop branch
  - `/create-pr --base=release/v2.0` → Creates PR to release branch
  - `/create-pr --japanese --base=develop` → Japanese PR to develop branch

## Update PR Support

**--update**: Updates an existing pull request instead of creating a new one

- Use when you've added commits to a branch that already has an open PR
- Finds the existing PR for the current branch
- Updates PR title and description based on all commits
- Useful after addressing review comments or adding more changes
- Examples:
  - `/create-pr --update` → Updates existing PR for current branch
  - `/create-pr --update --japanese` → Updates PR with Japanese description
- **Note**: Only works if an open PR exists for the current branch
- If no PR is found, will notify the user (does not create a new PR)

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
- 影響を受ける機能:[コミットにより影響を受ける機能]
- 影響を受けるファイル:[変更された主要ファイル]
- 破壊的変更:[あり/なし]

## テスト方法
1. [テスト手順1]
2. [テスト手順2]

## チェックリスト
- [ ] コードは正常に動作することを確認した
- [ ] 適切なテストを追加/更新した
- [ ] ドキュメントを更新した(必要な場合)
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
- Use ですます調 for paragraph-style sentences
- For bullet points, use である調 or noun-ending style (体言止め)
- Omit final punctuation in bullet points (no `。`)

**Escaping Rules (Important):**
- For GitHub MCP tools (`mcp__github__create_pull_request`, `mcp__github__update_pull_request`):
  - Pass `body` as raw Markdown text
  - Do NOT escape backticks in Markdown (use `` `code` ``, never `\`code\``)
  - If generated text contains `\` before backticks, normalize it to plain backticks before tool call
- For `gh` CLI commands:
  - Prefer `--body-file` to avoid shell-escaping issues
  - If inline body is unavoidable, use a single-quoted heredoc (`<<'EOF'`) so backticks are preserved as-is

### 5. Execution Steps

#### Standard Flow (Create New PR)

0. **Determine base branch**:
   - If `--base=<branch>` specified: Use the specified branch
   - Otherwise: Use repository default branch (`git symbolic-ref --short refs/remotes/origin/HEAD | sed 's@^origin/@@'`)

1. **Ensure changes are pushed**:
   ```bash
   git push -u origin [current branch name]
   ```

2. **Prepare PR content**:
   - Generate appropriate title summarizing commits
   - Create PR body following template or standard format
   - Analyze commits against the determined base branch
   - Apply escaping rules based on execution method (MCP vs `gh`)

3. **Create pull request**:
   ```
   mcp__github__create_pull_request:
   - title: [Generated title in selected language]
   - body: [Raw Markdown body in selected language; do NOT escape backticks]
   - head: [Current branch]
   - base: [Determined base branch from step 0]
   ```

4. **After creation**:
   - Provide PR URL
   - Confirm success
   - Explain any errors clearly

#### Update Flow (--update flag)

0. **Get current branch**:
   ```bash
   git branch --show-current
   ```

1. **Find existing PR for current branch**:
   ```
   mcp__github__list_pull_requests:
   - state: open
   - head: [repository owner]:[current branch]
   ```

2. **Verify PR exists**:
   - If no PR found: Notify user and exit (do NOT create new PR)
   - If PR found: Extract PR number and current base branch

3. **Ensure latest changes are pushed**:
   ```bash
   git push origin [current branch name]
   ```

4. **Prepare updated PR content**:
   - Generate new title summarizing all commits
   - Create new PR body following template or standard format
   - Analyze all commits against the PR's base branch
   - Apply escaping rules based on execution method (MCP vs `gh`)

5. **Update pull request**:
   ```
   mcp__github__update_pull_request:
   - pull_number: [PR number from step 2]
   - title: [Generated title in selected language]
   - body: [Raw Markdown body in selected language; do NOT escape backticks]
   ```

6. **After update**:
   - Provide PR URL
   - Confirm successful update
   - Explain any errors clearly

## Important Notes
- ONLY analyze committed changes (ignore uncommitted work)
- Notify if no commits exist between branches
- Focus on what was committed, not work in progress
- Be concise, avoid redundancy across sections
- **Without --update**: CREATE new PR using mcp__github__create_pull_request
- **With --update**: UPDATE existing PR using mcp__github__update_pull_request
- **With --update**: If no PR exists, notify user and DO NOT create new PR
- **Use AskUserQuestionTool** when you need clarification on:
  - Whether certain commits should be included in the PR
  - How to categorize or describe ambiguous changes
  - Which base branch to use if not specified and multiple options exist
