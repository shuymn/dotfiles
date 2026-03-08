# Codex Workflow Agents

このディレクトリは、workflow 用 agent 定義の正本です。
実行時の配線先ではなく、role ごとの責務と使い分けを管理するための置き場として使います。

## 基本の順番

1. root session が workflow mode に入る
2. `design-drafter`
3. `design-reviewer`
4. `plan-drafter`
5. `plan-reviewer`
6. `task-implementer`
7. `dod-rechecker`
8. `adversarial-verifier`
9. `completion-auditor` (`completion_gate` が必要なとき)

`repo-explorer` と `docs-researcher` は補助 role です。
必要な phase で親 agent が随時起動し、主に調査と情報収集を担当します。

## 使い方

- 専用の orchestrator agent は使いません。通常は root session がそのまま動きます。
- ユーザーが workflow を明示したとき、または design / plan / task / Ralph artifact を渡したときだけ、root session が workflow mode に入ります。
- workflow mode では、root session が現在の phase を判断し、対応する role を明示的に起動します。
- `design-doc(create)` と `decompose-plan(create)` でユーザーに質問するのは親 agent だけです。
- `repo-explorer` は repo 内の事実確認、`docs-researcher` は外部 docs の確認に使います。
- `design-reviewer`、`plan-reviewer`、`dod-rechecker`、`adversarial-verifier`、`completion-auditor` は独立性を保って使います。
- production code を編集させるのは `task-implementer` だけです。

### phase ごとの使わせ方

- 設計を始めるとき:
  root session が必要に応じて `repo-explorer` / `docs-researcher` を使い、要件整理後に `design-drafter` を起動します。
- 設計を見直すとき:
  root session が `design-reviewer` を独立に起動します。
- 実装計画に分解するとき:
  root session が `plan-drafter` を起動します。
- 実装計画を見直すとき:
  root session が `plan-reviewer` を独立に起動します。
- 実装するとき:
  root session が対象 task を決めたうえで `task-implementer` を起動します。
- 完了条件を再確認するとき:
  root session が `dod-rechecker` を起動します。
- 攻撃的に検証するとき:
  root session が `adversarial-verifier` を起動します。
- 最終完了を監査するとき:
  root session が `completion-auditor` を起動します。これは plan や Ralph metadata が `completion_gate` を要求するときに使います。

## 各 agent の説明

- `repo-explorer`: ローカル repo の調査役です。ファイル、設定、テスト、スクリプトを読み、実装判断の材料を集めます。
- `docs-researcher`: 外部ドキュメント調査役です。公式 docs や一次情報を確認し、要点だけ返します。
- `design-drafter`: `design-doc` の create 担当です。親が整理した要件をもとに設計草案を作ります。
- `design-reviewer`: `design-doc` の review 担当です。設計草案を独立に見直します。
- `plan-drafter`: `decompose-plan` の create 担当です。承認済み design から実行可能な plan に分解します。
- `plan-reviewer`: `decompose-plan` の review 担当です。plan の task shape、整合性、gate を独立に確認します。
- `task-implementer`: `execute-plan` の implement 担当です。production code を編集できる唯一の role です。
- `dod-rechecker`: `execute-plan` の dod-recheck 担当です。DoD を独立に再確認します。
- `adversarial-verifier`: `adversarial-verify` 担当です。DoD 通過後に攻撃的な観点で検証します。
- `completion-auditor`: `completion-audit` 担当です。task 完了ではなく、製品レベルの完了主張を最終監査します。

## 運用メモ

- helper の並列化は `repo-explorer` と `docs-researcher` を中心に使います。
- review / recheck / verify / audit 系は独立性を優先して扱います。
- production code の編集 owner は常に `task-implementer` だけです。
- `completion-auditor` は public CLI/API/runtime/release claim の最終 closure gate です。

## よくある起動パターン

- 新しい設計を作る:
  root session → `repo-explorer` / `docs-researcher` → `design-drafter` → `design-reviewer`
- 設計から plan を作る:
  root session → `plan-drafter` → `plan-reviewer`
- 1 task だけ実装する:
  root session → `task-implementer` → `dod-rechecker`
- 重要な task を最後まで検証する:
  root session → `task-implementer` → `dod-rechecker` → `adversarial-verifier`
- 製品レベルの完了主張まで閉じる:
  root session → `task-implementer` → `dod-rechecker` → `adversarial-verifier` → `completion-auditor`
