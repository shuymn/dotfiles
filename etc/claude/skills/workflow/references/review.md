<!-- do not edit: generated from skills/src/workflow/references/review.md; edit source and rebuild -->

# Workflow: Review

## Review Policy

review は「全部読む」から「危険箇所だけ見る」に変える。

- default は full diff review ではなく gate 通過
- 人間が見るのは public API、data loss、security、cost、migration、destructive operation などの高リスク境界
- churn が大きいときは全文 review ではなく、変更境界と異常点を sampling する
- AI には diff summary、risk summary、実行した gate、未解決の不確実性を返させる

レビュー不能な量のコードが出ることを前提に、review で品質を担保しようとしない。品質は executable gate と rollback しやすい変更単位で担保する。

---

## Human Role

人間の仕事は次に限定する。

- 何を達成したいかを決める
- 破ってはいけない constraints を決める
- 危険な変更の許可/不許可を決める
- escalation を裁く
- milestone 単位で成果を評価する

人間は、毎回の分解、毎回の実装順決め、毎回の diff 精読の担当にならない。

---

## ADR Policy

ADR は「未来の実装者が、その判断を知らないと同じ議論をやり直す」場合だけ残す。

<!-- 最低限次を書く。 -->

- `Context`
- `Decision`
- `Rejected Alternatives`
- `Consequence`
- `Revisit trigger`

次は ADR にしない。

- 現状のコードを読めばわかること
- 一時的な作業計画
- 実行していない想像上の運用
- test や script に落とせる手順

---

## Anti-Patterns

- 文書 review を通すための文書を書く
- 実装前に詳細な計画を固定し、AI をその写経係にする
- 横分解の task を backlog の主単位にする
- 実行不能な手順書を残す
- code と prose の二重管理を許す
- private methods の unit test を増やす
- 人間が毎回 task decomposition と diff review を抱える

---

<!-- `Workflow` の目的は、文書を増やして人間が監督することではない。`code/tests/scripts` を中心に据え、AI が自走できる最小の縦テーマへ圧縮し、人間は `goal / constraints / escalation` だけを握ることにある。 -->
