# Create Pull Request on GitHub from Committed Changes

You are running the /create-pr extension. Create or update a GitHub pull request from committed changes.

## Tool Policy During This Workflow

- Use only inspection tools, `bash`/`shell_command`, read-only subagents, and the temp-file helper for PR body files.
- Do not use `apply_patch`, direct file edit tools, or workspace write tools.
- `spawn_subagent` is read-only in this workflow.
- Shell commands are restricted to read-only inspection plus the workflow-required side effects: `git push`, `gh pr create`, and `gh pr edit`.
- When `--body-file` is needed, write the body with `workflow_write_temp_file`; do not create body files in the workspace.

## Scope

- Analyze committed changes only.
- Ignore uncommitted work except to warn the user that it will not be included.
- Requires a GitHub repository and GitHub authentication.
- Push the current branch before creating/updating the PR.

## Interactive Options

The extension asks for options interactively. The selected options shown in the prompt are authoritative.

Language:

- English: create PR title/body in English.
- Japanese: create PR title/body in Japanese.

Mode:

- Create: create a new PR.
- Update: update an existing open PR for the current branch. If no PR exists, notify the user and do not create a new one.

Base branch:

- In create mode, use the selected base branch.
- In update mode, use the existing PR's base branch.

## Required Context Commands

Verify git/GitHub state with live commands before creating or updating:

```bash
git branch --show-current
git branch -r
git symbolic-ref --short refs/remotes/origin/HEAD
git rev-parse --show-toplevel
git status -sb
```

For committed changes, replace `<base>` with the selected base branch or existing PR base:

```bash
git log origin/<base>..HEAD --oneline
git rev-list --count origin/<base>..HEAD
git diff --name-status origin/<base>..HEAD
git diff --shortstat origin/<base>..HEAD
git diff origin/<base>..HEAD
git log origin/<base>..HEAD --format="### %s%n%n%b%n"
git log origin/<base>..HEAD --format="%an <%ae>"
```

PR templates:

```bash
cat .github/pull_request_template.md
cat .github/PULL_REQUEST_TEMPLATE.md
```

If neither template file exists, continue without a template.

Project information:

```bash
head -50 README.md
```

If README.md does not exist, continue without README context.

## Analyze Committed Changes

- Review all commits between current branch and base branch.
- Understand intent from commit messages and diff.
- Identify types and scope of changes.
- Check for breaking changes.
- Classify commits as feature, fix, refactor, docs, chore, etc.
- Notify the user if there are no commits between the current branch and base.

## PR Body Format

- If `.github/pull_request_template.md` or `.github/PULL_REQUEST_TEMPLATE.md` exists, follow it strictly.
- Fill sections based on committed changes only.
- Delete empty sections when appropriate.
- Maintain checklist format (`- [ ]`).
- If no template exists, use the standard format below.

## Standard Format (English)

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

## Standard Format (Japanese)

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

## Writing Guidelines

English:

- Use clear, concise English.
- Keep code references and file paths as-is.
- Be direct and professional.
- Wrap @ symbols in code/paths with backticks to prevent mentions: `@import`, `path/@file`.

Japanese:

- Use appropriate technical Japanese.
- Keep English proper nouns, libraries, functions, and paths as-is.
- Use clear Japanese without honorifics.
- Use ですます調 for paragraph-style sentences.
- For bullet points, use だ・である調 or noun-ending style (体言止め).
- Omit final punctuation in bullet points (no `。`).

Escaping:

- Prefer `gh pr create --body-file <file>` and `gh pr edit --body-file <file>` to avoid shell escaping issues.
- Create `<file>` with `workflow_write_temp_file`; it must be under the OS temp directory, not the workspace.
- Do not use heredocs or shell redirection for PR bodies in this workflow.
- Do not escape Markdown backticks unnecessarily.

## Create Flow

1. Determine current branch:
    ```bash
    git branch --show-current
    ```
2. Use the selected base branch.
3. Ensure there are commits to include:
    ```bash
    git log origin/<base>..HEAD --oneline
    ```
4. Push current branch:
    ```bash
    git push -u origin <current-branch>
    ```
5. Generate PR title and body from committed changes.
6. Create the PR, preferably with GitHub CLI:
    ```bash
    gh pr create --base <base> --head <current-branch> --title "<title>" --body-file <body-file>
    ```
7. Provide the PR URL and summarize success.

## Update Flow

1. Determine current branch:
    ```bash
    git branch --show-current
    ```
2. Find the existing open PR for the current branch:
    ```bash
    gh pr view --json number,url,baseRefName,headRefName,title,state
    ```
    If no open PR exists, notify the user and do not create a new PR.
3. Push latest changes:
    ```bash
    git push origin <current-branch>
    ```
4. Analyze all commits against the PR's base branch.
5. Generate updated title and body from committed changes.
6. Update the PR:
    ```bash
    gh pr edit <number> --title "<title>" --body-file <body-file>
    ```
7. Provide the PR URL and summarize success.

## Important Notes

- In create mode, create a new PR.
- In update mode, update an existing PR only; do not create a new PR if none exists.
- Explain errors clearly.
- Ask the user when you need clarification about commit inclusion, categorization, or ambiguous PR content.
