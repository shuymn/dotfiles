<!-- do not edit: generated from skills/src/workflow/references/exec.md; edit source and rebuild -->

# Workflow: Execute

## Standard Loop Phase B: Execute (per Theme, repeat)

<!-- 重要なのは、自然言語の計画を厚くすることではなく、AI が 1 回の作業で扱える最小の実行単位に圧縮すること。 -->

7. `TODO.md` から 1 つの縦テーマを切る。
8. そのテーマを表す `Executable doc` を先に作る。
9. AI に `Executable doc` を先に失敗させ、`Red -> Green -> Refactor` の順で実装と整理を進めさせる。
10. gate が通るまで AI が自走する。
11. 人間は escalation 条件に当たったときだけ介入する。
12. 変更後、残す価値がある差分だけを `TODO.md` と ADR に反映する。
13. 一時メモ、途中の計画、賞味期限切れの prose は削除する。

---

## Theme Shape

`TODO.md` の 1 `Theme` は最低でも次を持つ。

- `Theme`
  何が前進するか。
- `Outcome`
  終わると外から何が変わるか。
- `Executable doc`
  先に書く test / fixture / script / check command。
- `Why not split vertically further?`
  なぜこの粒度で止めるのか。
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
  - Why not split vertically further?: ...
  - Escalate if: ...
```

`Executable doc` が定まらない `Theme` は、まだ大きすぎるか曖昧すぎるか、`blocking` な `Open Question` が残っている。`Why not split vertically further?` に答えられない `Theme` もまだ大きすぎる。先に分割するか、`Open Question` を潰す。

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

- `static` -- 型、lint、format、禁止依存、schema check
  - 選択条件: 全 `Theme` で必須
- `integration` -- `public contract`、境界接続、状態遷移
  - 選択条件: `public contract` を触るなら原則必須
- `system` -- 主要シナリオ、e2e、stop-ship 条件
  - 選択条件: ユーザー価値や運用シナリオを直接変えるなら追加
- `unit` -- 局所補強が必要なときだけ
  - 選択条件: 追加コストに見合う場合だけ入れる

gate は replay 可能でなければならない。結果だけ書かれた prose は evidence とみなさない。
