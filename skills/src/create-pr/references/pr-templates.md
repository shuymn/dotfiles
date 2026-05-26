# PR Body Templates

These are fallback templates for repositories without `.github/pull_request_template.md`.
Keep the body short: explain what changed, why it changed, and how it was verified.
Delete any section that would only repeat the diff or say "none".

## Standard Format (English)

```markdown
## Summary
[1-3 concise bullets or sentences covering the major user-visible or reviewer-relevant changes]

## Why
[Context, problem, trade-off, or decision that is not obvious from the code]

## Testing
- [Command/manual check and result]
```

Add only when relevant:

```markdown
## Reviewer Notes
- [Where to start reviewing, known limitation, follow-up, rollout, or breaking change]
```

## Standard Format (Japanese / --japanese)

```markdown
## 概要
[ユーザーやレビュアーに重要な変更を1-3個の簡潔な箇条書きまたは文で説明]

## 背景
[コードだけでは分からない文脈、問題、判断、トレードオフ]

## テスト
- [実行したコマンド/手動確認と結果]
```

必要な場合のみ追加:

```markdown
## レビュアー向けメモ
- [最初に見る場所、既知の制約、フォローアップ、ロールアウト、破壊的変更]
```
