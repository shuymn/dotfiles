---
name: workflow
description: >-
  Use when the user invokes /workflow.
  Injects project workflow methodology as context.
  Accepts argument: plan, exec, review (default: all).
disable-model-invocation: true
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

## 共有契約

### Theme Contract

`TODO.md` の各 `Theme` は最低でも次を持つ。

- `Theme` -- 何が前進するか
- `Outcome` -- 終わると外から何が変わるか
- `Goal` -- 今回達成したい外部結果
- `Must Not Break` -- 壊してはいけない境界、契約、運用条件
- `Non-goals` -- 今回保証しないこと、広げないこと
- `Acceptance` -- 合格条件と閾値
- `Evidence` -- どの test / script / metric / check で合否を見るか。その replay 手順と trust metadata の正本
- `Gates` -- この `Theme` で使う gate 名。`Gate Model` の語彙だけを使い、最低要件を満たす
- `Executable doc` -- plan で先に書く、実装前は失敗し実装後は通る replay 可能な test / fixture / script / check command
- `Why not split vertically further?` -- これ以上縦に分けない理由
- `Escalate if` -- 人間判断が必要になる条件

これらは独立 artifact ではなく、`TODO.md` の各 `Theme` に入れる。
この contract に入らない説明は残さない。
`Evidence` は canonical home として `run`、`oracle`、`visibility`、`controls`、`missing`、`companion`、必要なら `notes` を持つ。`controls` と `missing` は常に `[]` 付きの集合表記で書き、空でも `[]` を使う。`controls` の語彙は `agent` と `context` だけに固定する。`companion` は常に明示し、`visibility=independent` なら `none`、`visibility=implementation-visible` なら replay 可能な独立 evidence を入れる。

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

### Role Boundary

- 人間は `goal / constraints / escalation` を握る。
- 人間は危険な変更の許可/不許可を決める。
- 人間は milestone 単位で成果を評価する。
- AI は分解、局所探索、実装を担う。
- AI は default で毎回の diff 精読を人間に要求しない。

### Gate Model

- gate は replay 可能な check 群であり、品質担保の主手段である。
- 各 `Theme` は `Theme Contract` から必要な gate を 1 つではなく複数選ぶ。
- `coverage` は補助指標であり、主指標ではない。test が実装をなぞると、高 coverage でも壊れた oracle のまま通る。
- 第一級の契約は `public contract` と主要シナリオを表す `integration` / `system` に置く。
- `public contract` を検証する evidence は、`Executable doc`、fixture、外部契約、期待値 table のような独立 oracle を持つものを優先する。
- test は実装ではなく `Theme Contract`、`Executable doc`、`Acceptance`、`Evidence.oracle` を見て書く。
- test や別視点 review の信頼度は `Evidence.controls` に載る担当 agent 分離と context 分離で上げる。
- unit test は実装導入、局所補強、デバッグ隔離のために使い、契約の canonical source にはしない。
- `benchmark`、`coverage`、`mutation`、`independent AI review` は取りこぼしや精度を補助確認するために使い、上位契約の代替にはしない。

利用可能な gate:

- `static` -- 型、lint、format、禁止依存、schema check
- `integration` -- `public contract`、境界接続、状態遷移
- `system` -- 主要シナリオ、e2e、stop-ship 条件
- `benchmark` -- 性能制約、回帰閾値、処理量制約
- `coverage` / `diff coverage` -- 到達確認、未検証領域の補助把握
- `mutation` -- 検知力確認。高 coverage でも壊れた oracle を見抜く補助
- `independent AI review` -- 独立視点の補助確認
- `unit` -- 局所補強が必要なときだけ

最低要件:

- `static` は常に必須
- `public contract` を触るなら `integration` は必須
- ユーザー価値や運用シナリオを直接変えるなら `system` か同等の証拠は必須
- `Theme Contract` の `Gates` は最低要件を満たさなければならない
- 必要な gate を選べないなら escalation する

### Anti-Patterns

- 文書 review を通すための文書を書く
- 実装前に詳細な計画を固定し、AI をその写経係にする
- 横分解の task を backlog の主単位にする
- 実行不能な手順書を残す
- prose を正本にして code と二重管理する
- 実装を見て public contract test を量産し、executable な上位契約や独立 oracle を unit test 群だけで代替しようとする
- `Evidence` に trust metadata を残さず、test や review を independent と主張する
- private methods の unit test を増やす
- `coverage`、benchmark、test、AI review の通過だけで検知力を推定し、close したことにする
- 人間が毎回 task decomposition と diff review を抱える
