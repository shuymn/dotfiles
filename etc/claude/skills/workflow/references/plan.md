<!-- do not edit: generated from skills/src/workflow/references/plan.md; edit source and rebuild -->

# Workflow: Plan

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

### 3. `docs/roadmap.md`

`IDEA.md` が大きく、いきなり `TODO.md` に落とすと粗すぎるときだけ作る。

- `Theme` 候補
- 大きな優先方向
- まだ着手しない論点の圧縮

実装詳細、task 分解、gate 詳細は書かない。

### 4. ADR ( `docs/adr/<topic>.md` )

コードから復元しにくい判断だけを書く。

- なぜその制約や方針を採ったか
- 何を捨てたか
- どこで見直すか

<!-- 実装詳細、現状説明、コードの言い換えは書かない。役目を終えた prose は残さず、置換か削除を優先する。 -->

### 5. Architecture Baseline

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

<!-- `docs/roadmap.md` は optional artifact とする。 -->
<!-- 重い `Design Doc` は default artifact にしない。必要になったときだけ一時的に使い、役目を終えたら削除または ADR へ圧縮する。 -->

---

## Standard Loop Phase A: Stabilize (once per project/phase)

<!-- `Goal / Constraints` の初期置き場は会話である。 -->
<!-- 最初の永続 artifact は `docs/roadmap.md`、`Architecture Baseline`、`TODO.md` のいずれかになる。 -->

1. `Goal / Constraints` を定める。
2. (if `IDEA.md` が大きい) `docs/roadmap.md` に `Theme` 候補を圧縮する。
3. (if 長距離で壊れやすい賭けがある) `Architecture Baseline` を作る。
4. `Open Questions` を `blocking | risk-bearing | non-blocking` に分類する。
5. `blocking` を `decision` または `spike` で潰す。
6. 再利用価値がある判断だけ ADR に残す。

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

各 `Open Question` は次のどれかに分類し、対応する処理方針に従う。

- `blocking` -- 未決だと TODO の `Executable doc` が書けない
  - 処理: TODO に進む前に必ず潰す
- `risk-bearing` -- 今すぐ着手はできるが、後で大きく壊れる可能性がある
  - 処理: 破綻コストが高いものだけ先に潰す
- `non-blocking` -- 今は決めなくてよい
  - 処理: TODO に持ち込まず、保留か削除する

潰し方は 2 つだけに絞る。

- `decision`
  情報が揃っており、今決めればよい
- `spike`
  小さな実装、検証、ベンチ、試作をしてから決める

`Open Question` を潰した結果のうち、未来の実装者が知らないと同じ議論を繰り返すものだけ ADR に残す。
