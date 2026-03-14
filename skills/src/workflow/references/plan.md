# Workflow: Plan

## Core Rules

- plan の役割は closure に必要な判断だけを先に固定することにある。完璧な設計、将来の抽象化、広すぎる roadmap はここで増やさない。

---

## Persistent Artifacts

- `Theme Backlog` -- `TODO.md`。未完了の縦テーマだけを置く
- `Roadmap` -- `docs/roadmap.md`。`IDEA.md` が大きく、優先方向の圧縮が必要なときだけ作る
- `ADR` -- `docs/adr/<topic>.md`。再利用価値がある判断だけ残す
- `Architecture Baseline` -- `docs/architecture.md`。先に固定しないと blocker 判定が揺れる長距離の賭けがあるときだけ作る

---

## Theme Contract Source

`Theme` schema の正本は [Theme Contract](../SKILL.md) である。ここでは `TODO.md` にどう書くかだけを補足する。

`Executable doc` は次を満たすものを選ぶ。

- `public contract` や user-facing behavior を触るなら、example、CLI replay、fixture replay、scenario test のような上位契約を直接 replay できる形を優先する
- unit test 群だけを `Executable doc` にして上位契約の代替にしない
- prose にしか存在しない手順は正本にせず、必要なら `test / script / command` に落としてから採用する
- test を主要 evidence に使うなら、`Evidence.oracle`、`Evidence.visibility`、`Evidence.controls`、`Evidence.missing`、`Evidence.companion` を先に決める
- `public contract` や主要シナリオを触る `Theme` では、可能なら `Evidence.controls=[agent,context]` を狙う

`Acceptance` は次だけを書く。

- `merge` / `close` の十分条件
- stop 条件
- 今回の blocker 判定に必要な条件

書かないもの:

- 将来の理想状態
- 一般改善
- polish
- follow-up に落とす non-blocking 論点

---

## Stabilize Loop

1. `Goal / Constraints` を定める。
2. 必要なら `Theme` 候補を圧縮する。
3. 必要なら `Architecture Baseline` で長距離の賭けを固定する。
4. `Open Questions` を `blocking | risk-bearing | non-blocking` に分類する。
5. `blocking` は `decision` または `spike` で唯一解が得られたときだけ解消し、それ以外は escalation する。
6. `risk-bearing` は今回の誤実装や誤判定に直結するものだけ先に扱う。
7. `non-blocking` は follow-up に落とし、今回の `Theme` に混ぜない。
8. 再利用価値がある判断だけ ADR に残す。
9. 実行に渡す `Theme Contract` を `TODO.md` に書く。`Gates` と `Executable doc` はこの step で最初に定義し、最低要件を満たすことを確認する。

`Theme Contract` は `Theme Backlog` の中に書き、別 artifact へ分けない。

---

## Architecture Baseline

作るのは、新規プロダクト、基盤変更、永続化、境界設計、技術選定のような長距離の賭けがあり、先に固定しないと blocker 判定が揺れるときだけ。

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
- 当面の closure に影響しない将来論

---

## Open Questions

- `blocking` -- 未決だと `Executable doc` または `Acceptance` が書けない。`TODO.md` に進む前に解消する
- `risk-bearing` -- 今すぐ進めるが、今回の誤実装や誤判定に直結する可能性がある。破綻コストが高いものだけ先に解消する
- `non-blocking` -- 今は決めなくてよい。follow-up に落とし、`TODO.md` に持ち込まない

解消手順:

1. まず自分で最適解を検討する。
2. `decision` または `spike` のどちらで解くかを決める。
3. 「これ以外ありえない」と言える選択肢が得られたときだけ、その案で解消する。
4. それ以外は escalation する。

使い分け:

- `decision` -- 情報が揃っており、今決めればよい
- `spike` -- 小さな実装、検証、ベンチ、試作をしてから決める

書式は次に固定する。

```md
- Question: ...
  - Class: `blocking | risk-bearing | non-blocking`
  - Resolution: `decision | spike`
  - Status: `resolved | escalated`
```

---

## ADR Policy

ADR は、未来の実装者がその判断を知らないと同じ議論をやり直す場合だけ残す。

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
- follow-up に落とせる non-blocking 論点
