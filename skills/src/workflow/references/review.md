# Workflow: Review

## Review Rules

- default は full diff review ではなく gate 通過
- churn が大きいときは全文 review ではなく、変更境界と異常点を sampling する
- `independent AI review` は primary gate ではなく補助チェックとして扱う
- 品質は [Gate Model](../SKILL.md) にある gate 名の正本と rollback しやすい変更単位で担保する

---

## Review Targets

最低限見る対象は次に絞る。

- `public contract` の差分
- `data model` と migration の差分
- `side effects` の差分
- `security boundary` と permission の差分
- `failure mode` と rollback 条件

ここに当てはまらない差分は、まず [Gate Model](../SKILL.md) と summary で扱う。

---

## Required Output

review では少なくとも次を返す。

- diff summary
- risk summary
- gate を選んだ根拠
- 実行した gate
- gate と evidence の対応
- 実行した evidence
- closure decision
- 残っている不確実性
- 必要なら追加で見るべき高リスク境界

`Gates Run` では [Gate Model](../SKILL.md) の語彙だけを使う。
`Gate Rationale` では `Goal / Must Not Break / Acceptance / public contract` からどの gate が必須になったかを短く示す。
`Gate Trace` では各 gate をどの evidence が満たしたかを示す。
`Evidence Run` では replay した command / test / report と結果を示す。
`Closure Decision` は `closable | not closable` のどちらかを返し、`closable` のときだけ `Theme` を `TODO.md` から外せる。

背景説明や一般論は返さない。

書式は次に固定する。

```md
## Diff Summary
## Risk Summary
## Gate Rationale
## Gates Run
## Gate Trace
## Evidence Run
## Closure Decision
## Remaining Uncertainty
## Extra Review Needed
```
