<!-- do not edit: generated from skills/src/workflow/references/exec.md; edit source and rebuild -->

# Workflow: Execute

## Execute Loop

7. `TODO.md` から実行対象の縦テーマを選ぶ。
8. そのテーマが [Theme Contract](../SKILL.md) を満たしていることを確認する。
9. `Goal / Must Not Break / Non-goals / Acceptance / Evidence / Gates` が整合しており、`Gates` が [Gate Model](../SKILL.md) の最低要件を満たすことを確認する。
10. AI に `Executable doc` をそのまま先に失敗させ、`Red -> Green -> Refactor` の順で実装と整理を進めさせる。
11. 選択済み gate が blocker を十分に潰すまで AI が自走する。
12. blocker が無くなり、選択済み gate が通ったら止まる。追加の polish や一般改善で loop を伸ばさない。
13. review がその `Theme` を closable と判断したときだけ `TODO.md` から外す。残す価値がある判断だけ ADR に反映する。
14. 一時メモ、途中の計画、賞味期限切れの prose は削除する。

---

## Theme Preconditions

実行前に対象 `Theme` が [Theme Contract](../SKILL.md) を満たしていることを確認する。

- `Executable doc` が空、replay 不可、または最初に fail しないなら plan に戻す
- `public contract` や user-facing behavior を触るのに `Executable doc` が unit test 群だけなら plan に戻す
- test を主要 evidence に使うのに `Evidence.oracle` / `Evidence.visibility` / `Evidence.controls` / `Evidence.missing` / `Evidence.companion` が無いなら plan に戻す
- `Evidence.visibility=independent` なのに `Evidence.companion!=none` なら plan に戻す
- `Evidence.visibility=implementation-visible` なのに `Evidence.companion=none` なら plan に戻す
- `Gates` が空、または [Gate Model](../SKILL.md) の最低要件を満たさないなら plan に戻す
- `Why not split vertically further?` に答えられないなら、先に分割する
- `blocking` な未解決事項が残っているなら、先に解消する

---

## Check Mapping

- `Goal` → `system` または `integration`
- `Must Not Break` → `integration`、`static`、必要なら `system`
- `Non-goals` → 実装、test、review を広げない境界
- `Acceptance` → pass/fail 条件、閾値、停止条件
- `Evidence` → replay 可能な command、test、metric、report と trust metadata
- `Gates` → 採用した gate 名と最低要件の充足
- `independent AI review` を使う場合、`Gates` に明示されていなければ `system` または `integration` の補助 evidence として扱う

証拠にならないもの:

- 結果だけを書いた prose
- 再実行できない確認
- 安心感のためだけに足した check

---

## Testing And Stop Rules

- テスト方針は `integration-first, system-when-needed` とする。
- `public contract` や主要シナリオを触る高リスク `Theme` では、可能なら subagent / multiagent を使って test 生成または別視点 replay を分離する。
- 担当 agent 分離や context 分離を確認できない場合は、`Evidence.visibility=implementation-visible` に downgrade し、`Evidence.missing` を更新する。
- unit test は実装導入、局所補強、デバッグ隔離のために使い、仕様の canonical source にはしない。
- bug fix では、まず失敗を再現する test か fixture を作る。
- prose で説明した手順は、最終的に test / script / command に変換する。
- 選択済み gate が通り、blocking issue が残っていないなら止まる。
- 根拠の弱い懸念を speculative fix に変換しない。
- non-blocking な改善案は原則この loop に混ぜず、必要なら follow-up に落とす。
- check を足すのは停止条件に必要な場合だけ。安心感のために gate を増やさない。

---

## Gate Replay

exec は plan で選ばれた `Gates` と `Executable doc` を replay する phase であり、gate 一覧や gate 選定を再定義しない。

- `Gates` が shared vocabulary を使っていることを確認する
- `Executable doc` と `Evidence` を replay して結果を埋める
- test を replay する前に、`Evidence.oracle` が実装ロジックの写しになっていないか確認する
- test / review を分離できたら `Evidence.controls` に `agent` と `context` を入れる
- 実行中に control を失ったら `Evidence.visibility=implementation-visible` に downgrade し、`Evidence.missing` を更新する
- `Evidence.visibility=implementation-visible` へ落ちて `Evidence.companion=none` のままなら exec を止めて plan に戻す
- `Evidence.visibility=implementation-visible` へ落ちたら、`Evidence.companion` に書かれた独立 evidence を replay する
- review で gate と evidence の対応を追える形に揃える

gate は replay 可能でなければならない。
