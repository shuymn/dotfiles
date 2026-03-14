<!-- do not edit: generated from skills/src/workflow/references/exec.md; edit source and rebuild -->

# Workflow: Execute

## Execute Loop

7. `TODO.md` から実行対象の縦テーマを選ぶ。
8. そのテーマが [Theme Contract](../SKILL.md) を満たしていることを確認する。
9. `Goal / Must Not Break / Non-goals / Acceptance / Evidence / Gates` が整合しており、`Gates` が [Gate Model](../SKILL.md) の最低要件を満たすことを確認する。
10. AI に `Executable doc` をそのまま先に失敗させ、`Red -> Green -> Refactor` の順で実装と整理を進めさせる。
11. gate が通るまで AI が自走する。
12. 人間は escalation 条件に当たったときだけ介入する。
13. review が `Closure Decision: closable` を返した `Theme` だけ `TODO.md` から外す。残す価値がある判断だけ ADR に反映する。
14. 一時メモ、途中の計画、賞味期限切れの prose は削除する。

---

## Theme Preconditions

実行前に対象 `Theme` が [Theme Contract](../SKILL.md) を満たしていることを確認する。

- `Executable doc` が空なら plan に戻し、exec では 0 から発明しない
- `Executable doc` が replay 可能な command / test / fixture になっていないなら plan に戻す
- `Executable doc` が最初に fail する spec でないなら plan に戻す
- `public contract` や user-facing behavior を触るのに `Executable doc` が unit test 群だけなら plan に戻す
- test を主要 evidence に使うのに `Evidence.oracle` / `Evidence.visibility` / `Evidence.controls` / `Evidence.missing` / `Evidence.companion` が無いなら plan に戻す
- `Evidence.visibility=independent` なのに `Evidence.companion!=none` なら plan に戻す
- `Evidence.visibility=implementation-visible` なのに `Evidence.companion=none` なら plan に戻す
- `Gates` が空、または [Gate Model](../SKILL.md) の最低要件を満たさないなら plan に戻す
- `Why not split vertically further?` に答えられないなら、先に分割する
- `blocking` な `Open Question` が残っているなら、先に解消する

---

## Check Mapping

各 `Theme` は最初に `Goal / Must Not Break / Non-goals / Acceptance / Evidence / Gates` を `checks` に写像する。

- `Goal` → `system` または `integration`
- `Must Not Break` → `integration`、`static`、必要なら `system`
- `Non-goals` → test 追加対象から外す境界として明記
- `Acceptance` → pass/fail 条件、閾値、停止条件
- `Evidence` → replay 可能な command、test、metric、report と trust metadata
- `Gates` → 採用した gate 名と最低要件の充足
- `independent AI review` を使う場合、`Gates` に明示されていなければ `system` または `integration` の補助 evidence として扱う

証拠にならないもの:

- 結果だけを書いた prose
- 再実行できない確認

---

## Testing Rules

テスト方針は `integration-first, system-when-needed` とする。

- `public contract` や主要シナリオを触る高リスク `Theme` では、exec が subagent / multiagent を自律的に使って test 生成または別視点 replay を分離する。
- 担当 agent 分離や context 分離を確認できない場合は、常に `Evidence.visibility=implementation-visible` に downgrade し、`Evidence.missing` を更新する。
- unit test は実装導入、局所補強、デバッグ隔離のために使う。
- unit test を仕様の canonical source にしない。
- private methods はテストしない。
- bug fix では、まず失敗を再現する test か fixture を作る。
- prose で説明した手順は、最終的に test / script / command に変換する。

---

## Gate Instantiation

gate 名と最低要件の正本は [Gate Model](../SKILL.md) を参照する。exec は plan で選ばれた `Gates` と `Executable doc` を replay する phase であり、gate 一覧や gate 選定を再定義しない。
`Executable doc` は plan の出力であり、exec では次だけを行う。

- `Gates` が shared vocabulary を使っていることを確認する
- `Executable doc` と `Evidence` を replay して結果を埋める
- test を replay する前に、`Evidence.oracle` が実装ロジックの写しになっていないか確認する
- `public contract` や主要シナリオを触る test / review では、原則 subagent / multiagent を自律的に使って test 生成または別視点 replay を分離する
- subagent で test / review を分けられたら `Evidence.controls` に `agent` を入れ、分離コンテキストで実行できたら `context` を入れる
- 実行中に `agent` または `context` の control を失ったら `Evidence.visibility=implementation-visible` に downgrade し、`Evidence.missing` を更新する
- 実行中に `Evidence.visibility=implementation-visible` へ落ちて `Evidence.companion=none` のままなら、その `Theme` の exec を止めて plan に戻す
- 実行中に `Evidence.visibility=implementation-visible` へ落ちたら、`Evidence.companion` に書かれた独立 evidence を replay する
- `independent AI review` を使う場合、`Gates` に明示したときだけ gate として扱い、それ以外は `system` または `integration` の補助 evidence として残す
- `Evidence` と `Gates Run` に同じ gate 名を使える形へ揃える
- review が `Closure Decision` を返せるよう `Gate -> Evidence` の対応を残す

gate は replay 可能でなければならない。
