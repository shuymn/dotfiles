<!-- do not edit: generated from skills/src/workflow/references/plan.md; edit source and rebuild -->

# Workflow: Plan

## Core Rules

- `code + tests + scripts` を `source of truth` とする。
- prose は `constraints` とコードから復元しにくい判断だけに使う。

---

## Persistent Artifacts

- `Source of Truth`
  - `code / tests / scripts`
  - 現在の挙動、`public contract`、再現手順、受け入れ条件を入れる
- `Theme Backlog`
  - `TODO.md`
  - 未完了の縦テーマだけを置く
  - `1 Theme = 1つの外から観測できる前進`
- `Roadmap`
  - `docs/roadmap.md`
  - `IDEA.md` が大きいときだけ作る
  - `Theme` 候補と優先方向だけを圧縮する
- `ADR`
  - `docs/adr/<topic>.md`
  - コードから復元しにくい判断だけを書く
- `Architecture Baseline`
  - `docs/architecture.md`
  - 長距離で破綻しやすい賭けがあるときだけ作る

---

## Theme Contract Source

`Theme` schema の正本は [Theme Contract](../SKILL.md) である。`plan.md` は field 定義を再掲せず、`TODO.md` にどう書くかだけを補足する。

`Executable doc` の決め方:

- `public contract` や user-facing behavior を触る `Theme` では、executable example、CLI replay、fixture replay、scenario test のような上位契約を直接 replay できる形を優先する
- unit test 群だけを `Executable doc` にして上位契約の代替にしない
- prose にしか存在しない手順は正本にせず、必要なら `test / script / command` に落としてから `Executable doc` に採用する
- test を主要 evidence に使うなら、`Evidence.oracle` に期待値の根拠を、`Evidence.visibility` に `independent | implementation-visible` を、`Evidence.controls` / `Evidence.missing` に分離状況を、`Evidence.companion` に独立 evidence か `none` を書く
- `mutation` と `independent AI review` は、test の独立性が弱いときに追加する補助 gate / evidence として選ぶ
- `public contract` や主要シナリオを触る `Theme` では、exec が subagent / multiagent を自律的に使って test 生成や別視点 review を分離し、`Evidence.controls=[agent,context]` を狙う
- subagent を使えない、または不要な `Theme` だけ `Evidence.visibility=implementation-visible` を選べるが、その場合も `Evidence.companion` を先に計画する
- test 生成や別視点 review を分離するなら、`Evidence.controls` には担当 agent 分離と context 分離だけを `[]` 付き集合で入れる
- 使えない control は `Evidence.missing` に残し、独立性の claim を弱める
- `test agent isolation` / `context separation` は高リスク `Theme` での標準運用だが、workflow 全体の必須 phase にはしない

---

## ADR Policy

ADR は「未来の実装者が、その判断を知らないと同じ議論をやり直す」場合だけ残す。

書式は次に固定する。

```md
## Context
## Decision
## Rejected Alternatives
## Consequence
## Revisit trigger
```

次は ADR にしない。

- 現状のコードを読めばわかること
- 一時的な作業計画
- 実行していない想像上の運用
- test や script に落とせる手順

---

## Stabilize Loop

1. `Goal / Constraints` を定める。
   - Artifact: `Theme Backlog` または `none`
2. (if `IDEA.md` が大きい) `Theme` 候補を圧縮する。
   - Artifact: `Roadmap` または `none`
3. (if 長距離で壊れやすい賭けがある) 長距離の賭けを固定する。
   - Artifact: `Architecture Baseline` または `none`
4. `Open Questions` を `blocking | risk-bearing | non-blocking` に分類する。
   - Artifact: `Architecture Baseline` の `Open Questions`、または `none`
5. `blocking` は `decision` または `spike` で唯一解が得られたときだけ解消し、それ以外は escalation する。
   - Artifact: 再利用価値がなければ `none`
6. 再利用価値がある判断だけ ADR に残す。
   - Artifact: `ADR` または `none`
7. 実行に渡す `Theme Contract` を `TODO.md` に書く。`Gates` と `Executable doc` はこの step で最初に定義し、最低要件を満たすことを確認する。
   - Artifact: `Theme Backlog` または `none`

永続 artifact を書かない step では `Artifact: none` を選ぶ。`Theme Contract` は `Theme Backlog` の中に書き、別 artifact へ分けない。

---

## Architecture Baseline

- 作るのは新規プロダクト、基盤変更、永続化、境界設計、技術選定のような長距離の賭けがあるときだけ。
- `TODO.md` の前段に置く。backlog にはしない。

書式は次に固定する。

```md
## Goal
## Constraints
## Core Boundaries
## Key Tech Decisions
## Open Questions
## Revisit Trigger
```

固定する対象:

- 技術選定
- 実行環境
- 永続化方式
- 境界の切り方
- データモデルの中心
- compatibility / migration 方針
- fail-closed にする条件

固定しない対象:

- 実装詳細
- モジュール細分
- helper 配置
- private API の形
- 当面の 1 手に影響しない将来論

---

## Open Questions

分類:

- `blocking` -- 未決だと `Executable doc` が書けない。`TODO.md` に進む前に解消する
- `risk-bearing` -- 今すぐ進めるが後で大きく壊れる可能性がある。破綻コストが高いものだけ先に解消する
- `non-blocking` -- 今は決めなくてよい。`TODO.md` に持ち込まない

解消手順は次に固定する。

1. まず自分で最適解を検討する。
2. `decision` または `spike` のどちらで解くかを決める。
3. 「これ以外ありえない」と言える選択肢が得られたときだけ、その案で解消する。
4. それ以外は escalation する。

解き方は `decision` か `spike` だけに絞る。

- `decision` -- 情報が揃っており今決めればよい
- `spike` -- 小さな実装、検証、ベンチ、試作をしてから決める

書式は次に固定する。

```md
- Question: ...
  - Class: `blocking | risk-bearing | non-blocking`
  - Resolution: `decision | spike`
  - Status: `resolved | escalated`
```

結果のうち、未来の実装者が知らないと同じ議論を繰り返すものだけ ADR に残す。
