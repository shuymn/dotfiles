<!-- do not edit: generated from skills/src/workflow/references/review.md; edit source and rebuild -->

# Workflow: Review

## Review Rules

- `Theme` の `Gates` に `independent AI review` が無い別視点 replay は gate ではなく補助 evidence として扱う。
- 分離された test / review は、agent 分離と context 分離を満たせたかで見る。
- `Evidence.visibility=implementation-visible` で `Evidence.companion=none` または `Evidence.companion` が未充足なら `not closable` とする。

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

blocker にできるのは、今回の差分または今回の `Theme` に結びつき、`merge` / `close` を止める高信頼なものだけである。

コード review の blocker:

- correctness regression
- security issue
- reliability / edge case failure
- API / schema / contract violation
- 明確な可観測バグ

文書 review の blocker:

- 事実誤認
- 手順誤り
- 用語不整合で意味が変わる箇所
- 読者を誤行動に導く曖昧さ
- 既存文書より悪化している箇所

---

## Test Failure Triage

- test が `Executable doc` または `Acceptance` に一致するなら、まず実装バグとして扱う。
- test が `Executable doc` または `Acceptance` に一致しないなら、まず test バグとして扱う。
- test と `Executable doc` / `Acceptance` の対応が説明できないなら、close せず escalation する。

---

## Required Output

review では少なくとも次を返す。

- verdict
- blocking issues
- gates run
- gate trace
- evidence run
- remaining uncertainty
- follow-up

`Verdict` では `Closure Decision: closable | not closable` を最初に返す。
`Blocking Issues` では high-confidence blocker を全件列挙する。無ければ `No blocking issues.` とだけ書く。
`Gates Run` では [Gate Model](../SKILL.md) の語彙だけを使う。
`Gate Trace` では gate と evidence の対応を書く。test を使うなら `Evidence.oracle`、`Evidence.visibility`、`Evidence.controls`、`Evidence.missing`、`Evidence.companion` の結果もここに入れる。
`Evidence Run` では replay した command / test / report と結果を書く。`Theme` の `Gates` に無い別視点 replay、`implementation-visible test`、`companion` replay、plan に戻した事実もここに入れる。
`Remaining Uncertainty` では blocker と断定できない不確実性だけを書く。不確実性を blocker や fix 提案へ膨らませない。
`Follow-up` は原則 `None.` とする。本当に必要な高信頼・差分直結の non-blocking 論点だけを少数書く。

背景説明や一般論は返さない。

書式は次に固定する。

```md
## Verdict
## Blocking Issues
## Gates Run
## Gate Trace
## Evidence Run
## Remaining Uncertainty
## Follow-up
```
