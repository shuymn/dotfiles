# Workflow: Review

## Review Rules

- churn が大きいときは全文 review ではなく、変更境界と異常点を sampling する
- `Theme` の `Gates` に `independent AI review` が無い別視点 replay は gate ではなく補助 evidence として扱う
- 分離された test / review は、agent 分離と context 分離を満たせたかで見る
- `Evidence.visibility=implementation-visible` で `Evidence.companion=none` または `Evidence.companion` が未充足なら `not closable` とする
- 品質は [Gate Model](../SKILL.md) にある gate 名の正本と rollback しやすい変更単位で担保する

---

## Review Targets

最低限見る対象は次に絞る。

- `public contract` の差分
- test の `oracle independence`
- `tautological test risk`
- `Evidence.controls` と `Evidence.missing`
- `independent AI review` を使うときも、対象は公開シグネチャ、主要シナリオ、失敗系のような上位契約に寄せる
- `data model` と migration の差分
- `side effects` の差分
- `security boundary` と permission の差分
- `failure mode` と rollback 条件

ここに当てはまらない差分は、まず [Gate Model](../SKILL.md) と summary で扱う。

---

## Test Failure Triage

- test が `Executable doc` または `Acceptance` に一致するなら、まず実装バグとして扱う
- test が `Executable doc` または `Acceptance` に一致しないなら、まず test バグとして扱う
- test と `Executable doc` / `Acceptance` の対応が説明できないなら、close せず escalation する

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
`Gate Rationale` では gate を選んだ根拠だけを短く示す。
`Gate Trace` では gate と evidence の対応を書く。test を使うなら `Evidence.oracle`、`Evidence.visibility`、`Evidence.controls`、`Evidence.missing`、`Evidence.companion` の結果もここに入れる。
`Evidence Run` では replay した command / test / report と結果を書く。`Theme` の `Gates` に無い別視点 replay、`implementation-visible test`、`companion` replay、plan に戻した事実もここに入れる。
`Closure Decision` は `closable | not closable` のどちらかを返す。

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
