# Workflow

<!-- 更新原則は append ではなく rewrite とする。新しい論点が出たら追記せず、全体を削って今の最小運用仕様だけを書き直す。 -->

## Position

<!-- この Workflow は、人間がローカルプランナーや常時レビュー担当になる前提を捨てる。 -->

- `code + tests + scripts` を `source of truth` とする。
- 実行も静的検査もできない自然言語文書は、原則として残さない。
- テストコードを第一級のドキュメントとみなす。
- 人間は `goal / constraints / escalation` を握り、局所探索と実装は AI に大きく委ねる。
- 全差分の精読は default にしない。通過条件は prose review ではなく executable gate で決める。

---

## Source of Truth

永続 artifact は次に絞る。

### 1. Code / Tests / Scripts

これが唯一の一次情報である。

- 現在の挙動
- `public contract`
- 再現手順
- 受け入れ条件

は、可能な限りコード、テスト、fixture、CLI、script に埋め込む。

### 2. `TODO.md`

未完了の縦テーマだけを持つ backlog。

- 1 `Theme` = 1つの外から観測できる前進
- 層、部品、工程都合の横分解を書かない
- 実装メモではなく、AI に渡す実行単位の入口として使う

### 3. ADR

コードから復元しにくい判断だけを書く。

- なぜその制約や方針を採ったか
- 何を捨てたか
- どこで見直すか

<!-- 実装詳細、現状説明、コードの言い換えは書かない。役目を終えた prose は残さず、置換か削除を優先する。 -->

### 4. Architecture Baseline

新規プロダクト、基盤変更、永続化、境界設計、技術選定のように、長距離で破綻しやすい賭けがあるときだけ作る。

<!-- これは重い `Design Doc` ではない。目的は、最終ゴールまでの詳細設計を固定することではなく、先に露出すべき賭けと `Open Questions` を短く固定することにある。 -->

<!-- 最低限次だけ持つ。 -->

- `Goal`
- `Non-goals`
- `Constraints`
- `Core boundaries`
- `Key tech decisions`
- `Open Questions`
- `Revisit trigger`

<!-- `Roadmap` と `Design Doc` は default artifact にしない。必要になったときだけ一時的に使い、役目を終えたら削除または ADR へ圧縮する。 -->

---

## Standard Loop

<!-- `Goal / Constraints` の初期置き場は会話である。 -->
<!-- 最初の永続 artifact は `Architecture Baseline` または `TODO.md` のどちらかになる。 -->

1. `Goal / Constraints` を定める。
2. 長距離で壊れやすい賭けがあるなら `Architecture Baseline` を作る。
3. `Open Questions` を `blocking | risk-bearing | non-blocking` に分類する。
4. `blocking` を `decision` または `spike` で潰す。
5. 再利用価値がある判断だけ ADR に残す。
6. 安定した面の上で `TODO.md` から 1 つの縦テーマを切る。
7. そのテーマを表す `Executable doc` を先に作る。
8. AI に `Executable doc` を先に失敗させ、`Red -> Green -> Refactor` の順で実装と整理を進めさせる。
9. gate が通るまで AI が自走する。
10. 人間は escalation 条件に当たったときだけ介入する。
11. 変更後、残す価値がある差分だけを `TODO.md` と ADR に反映する。
12. 一時メモ、途中の計画、賞味期限切れの prose は削除する。

<!-- 重要なのは、自然言語の計画を厚くすることではなく、AI が 1 回の作業で扱える最小の実行単位に圧縮すること。 -->

---

## Architecture Baseline

<!-- `Architecture Baseline` は、長距離で効く賭けだけを先に固定するための薄い初期設計である。 -->

<!-- ここで扱うのは、後から変えると高くつくものに限る。 -->

固定する項目:

- 技術選定
- 実行環境
- 永続化方式
- 境界の切り方
- データモデルの中心
- compatibility / migration 方針
- fail-closed にする条件

<!-- 逆に、次はここで固定しない。 -->

固定しない項目:

- 実装詳細
- モジュール細分
- helper 配置
- private API の形
- 当面の 1 手に影響しない将来論

<!-- `Architecture Baseline` は TODO の前段に置くが、backlog そのものにはしない。 -->

---

## Open Questions

<!-- `Open Questions` は独立した重い工程ではない。`Architecture Baseline` の中で見つかった未解決の重要論点である。 -->

各 `Open Question` は次のどれかに分類する。

- `blocking`
  未決だと TODO の `Executable doc` が書けない
- `risk-bearing`
  今すぐ着手はできるが、後で大きく壊れる可能性がある
- `non-blocking`
  今は決めなくてよい

処理方針は次。

- `blocking`
  TODO に進む前に必ず潰す
- `risk-bearing`
  破綻コストが高いものだけ先に潰す
- `non-blocking`
  TODO に持ち込まず、保留か削除する

潰し方は 2 つだけに絞る。

- `decision`
  情報が揃っており、今決めればよい
- `spike`
  小さな実装、検証、ベンチ、試作をしてから決める

`Open Question` を潰した結果のうち、未来の実装者が知らないと同じ議論を繰り返すものだけ ADR に残す。

---

## Theme Shape

`TODO.md` の 1 `Theme` は最低でも次を持つ。

- `Theme`
  何が前進するか。
- `Outcome`
  終わると外から何が変わるか。
- `Executable doc`
  先に書く test / fixture / script / check command。
- `Escalate if`
  人間判断が必要になる条件。

最小形は次。

```md
- [ ] Theme: ...
  - Outcome: ...
  - Executable doc: `...`
  - Acceptance (EARS):
    - When ...
    - If ...
  - Escalate if: ...
```

`Executable doc` が定まらない `Theme` は、まだ大きすぎるか曖昧すぎるか、`blocking` な `Open Question` が残っている。先に分割するか、`Open Question` を潰す。

---

## Testing Policy

テスト方針は `integration-first, system-when-needed` とする。

- 仕様の本体は `system` または `integration` に寄せる。
- unit test は実装導入、局所補強、デバッグ隔離のために使う。
- unit test を仕様の canonical source にしない。
- private methods はテストしない。
- bug fix では、まず失敗を再現する test か fixture を作る。
- prose で説明した手順は、最終的に test / script / command に変換する。

<!-- 言い換えると、自然言語ドキュメントを多重管理するのではなく、実行可能な形へ落としたものを document とみなす。 -->

---

## Gate Policy

完全レビューは前提にしない。gate を強くする。

最低 gate は `Theme` ごとに必要なものだけ選ぶ。

- `static`
  型、lint、format、禁止依存、schema check
- `unit`
  局所補強が必要なときだけ
- `integration`
  `public contract`、境界接続、状態遷移
- `system`
  主要シナリオ、e2e、stop-ship 条件

基本は次。

- 全 `Theme` で `static` は必須
- `public contract` を触るなら `integration` は原則必須
- ユーザー価値や運用シナリオを直接変えるなら `system` を追加
- `unit` は追加コストに見合う場合だけ入れる

gate は replay 可能でなければならない。結果だけ書かれた prose は evidence とみなさない。

---

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

## One Line Summary

<!-- `Workflow` の目的は、文書を増やして人間が監督することではない。`code/tests/scripts` を中心に据え、AI が自走できる最小の縦テーマへ圧縮し、人間は `goal / constraints / escalation` だけを握ることにある。 -->
