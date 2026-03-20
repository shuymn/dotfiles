---
name: workflow
description: >-
  Use when the user invokes /workflow.
  Injects project workflow methodology as context.
  Accepts argument: plan, exec, review (default: all).
allowed-tools: [Read]
---

<!-- do not edit: generated from skills/src/workflow/SKILL.md; edit source and rebuild -->


## パス解決

- `<skill-root>` はこの `SKILL.md` を含むディレクトリを指す。
- `references/...` は呼び出し元のカレントディレクトリではなく、`<skill-root>` 基準で解決する。

## 引数ディスパッチ

`$ARGUMENTS` に応じて読む reference を決める。

- `$ARGUMENTS` が `plan` で始まる → [references/plan.md](references/plan.md) だけ読む
- `$ARGUMENTS` が `exec` で始まる → [references/exec.md](references/exec.md) だけ読む
- `$ARGUMENTS` が `review` で始まる → [references/review.md](references/review.md) だけ読む
- `$ARGUMENTS` が空、または未定義の値 → [references/plan.md](references/plan.md), [references/exec.md](references/exec.md), [references/review.md](references/review.md) をすべて読む

一致した file を読み、この session の plan / exec / review の運用ルールとして扱う。

## Core Stance

- workflow の主理論は `thin spec, thick checks` である。
- spec は薄く保つ。prose は `constraints`、復元しにくい判断、停止条件だけに使う。
- 品質担保は prose ではなく、replay 可能な checks / gates / evidence に寄せる。
- `thick checks` は量産ではない。高信号で replay 可能な checks を厚く持つことを指す。
- 最適化対象は人間向けの読みやすさではなく、`LLM -> artifact -> LLM` の往復でミスリードしにくい契約である。
- closure 判定は改善案の列挙ではなく、`merge` / `close` を止める blocker が残っているかを見る。
- blocker は高信頼で、今回の差分または今回の `Theme` に結びつくものだけを扱う。
- non-blocking な改善案、一般論、将来の抽象化、差分外の話は原則抑制する。
- 不確実なら escalation する。推測で blocker や fix を発明しない。
- 人間は `goal / constraints / escalation` を握る。AI は分解、局所探索、実装、check replay、closure judgment を担う。

## 共有契約

### Theme Contract

`TODO.md` の各 `Theme` は最低でも次を持つ。

- `Theme` -- `1 Theme = 1つの外から観測できる前進`
- `Outcome` -- 終わると外から何が変わるか
- `Goal` -- 今回達成したい外部結果だけ
- `Must Not Break` -- 今回の `merge` / `close` を止める blocker 境界
- `Non-goals` -- 今回扱わない改善、別 PR に送る改善、広げない論点
- `Acceptance` -- 十分条件と停止条件だけ
- `Evidence` -- blocker / no-blocker を判定する replay 手順と trust metadata の正本
- `Gates` -- `Gate Model` の語彙だけを使い、量ではなく信号強度で選ぶ
- `Executable doc` -- 実装前は失敗し実装後は通る replay 可能な spec。`merge` / `close` 判定に直結するものだけを置く
- `Why not split vertically further?` -- これ以上縦に分けない理由
- `Escalate if` -- AI が安全に閉じられない条件

これらは独立 artifact ではなく、`TODO.md` の各 `Theme` に入れる。この contract に入らない説明は残さない。
`Evidence` は `run`、`oracle`、`visibility`、`controls`、`missing`、`companion`、必要なら `notes` を持つ。`controls` と `missing` は常に `[]` を使い、語彙は `agent` と `context` だけに固定する。`visibility=independent` なら `companion=none`、`visibility=implementation-visible` なら replay 可能な独立 evidence を `companion` に入れる。

書式は次に固定する。

```md
- [ ] Theme: ...
  - Outcome: ...
  - Goal: ...
  - Must Not Break: ...
  - Non-goals: ...
  - Acceptance (EARS):
    - When ...
    - If ...
  - Evidence: `run=...; oracle=...; visibility=independent; controls=[agent,context]; missing=[]; companion=none; notes=...`
  - Gates: `static`, `integration`
  - Executable doc: `...`
  - Why not split vertically further?: ...
  - Escalate if: ...
```

### Gate Model

- gate は replay 可能な check 群であり、`thin spec, thick checks` を成立させる主手段である。
- 各 `Theme` は必要な gate を複数選べるが、十分な判定に必要な最小高信号セットに絞る。
- 第一級の契約は `public contract` と主要シナリオを表す `integration` / `system` に置く。
- test は実装ではなく `Theme Contract`、`Executable doc`、`Acceptance`、`Evidence.oracle` を見て書く。
- test や別視点 review の信頼度は `Evidence.controls` の agent 分離と context 分離で上げる。
- unit test は実装導入、局所補強、デバッグ隔離のために使い、契約の canonical source にはしない。
- `benchmark`、`coverage`、`mutation`、`independent AI review` は補助確認であり、上位契約の代替には使わない。

利用可能な gate:

- `static` -- 型、lint、format、禁止依存、schema check
- `integration` -- `public contract`、境界接続、状態遷移
- `system` -- 主要シナリオ、e2e、stop-ship 条件
- `benchmark` -- 性能制約、回帰閾値、処理量制約
- `coverage` / `diff coverage` -- 到達確認、未検証領域の補助把握
- `mutation` -- 検知力確認の補助
- `independent AI review` -- 独立視点の補助確認
- `unit` -- 局所補強が必要なときだけ

最低要件:

- `static` は常に必須
- `public contract` を触るなら `integration` は必須
- ユーザー価値や運用シナリオを直接変えるなら `system` か同等の証拠は必須
- `Theme Contract` の `Gates` は最低要件を満たさなければならない
- 必要な gate を選べないなら escalation する

### Anti-Patterns

- prose を厚くして安心しようとする
- 文書 review を通すための文書を書く
- 実装前に詳細な計画を固定し、AI をその写経係にする
- 横分解の task を backlog の主単位にする
- 実行不能な手順書を残す
- gate を増やすこと自体を目的化する
- `Evidence` に trust metadata を残さず、test や review を independent と主張する
- `coverage`、benchmark、test、AI review の通過だけで検知力を推定し、close したことにする
- low-signal な指摘まで blocker に昇格する
- blocker と non-blocker を同じ粒度で増殖させる
