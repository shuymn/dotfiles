# stack の cycle の結果ファイル

`scripts/stack-cycle`（launchd の `stack-cycle` ジョブ、`nix/home/profiles/dev.nix`）が `~/.local/state/stack/cycle/` に書き、statusline（`home/dot_claude/executable_statusline.sh.tmpl` の `comp_cycle`）とオーナーが読む。このディレクトリは stack の状態ルートの下にあるが、stack は何も書かず、ファイルと形式はこのリポジトリが持つ（`shuymn/stack` の `docs/design/phase2-core.md` §2.1）。cycle の拡張と `observe/latest.json` は `shuymn/stack` の `docs/design/phase3-cycle.md` にある。テストは `tests/test_stack_cycle.py` と `tests/test_statusline.py`。

## 有効な実行

ジョブは `stack run cycle --ext observe` の後に `stack run cycle --ext improve` を走らせ、次をすべて満たすときだけ有効とする。

- 2 回とも終了コード 0 で、`stage` が `cycle`、`status` が `pass` か `warn` の JSON オブジェクトを 1 つだけ出す。
- その `results` は呼んだ拡張の結果 1 件だけで、その拡張自身が答えたもの（`error` が空、`status` が `pass` か `warn`、`findings` が配列）。
- observe に `latest-not-written` の finding が無く、`observe/latest.json` の `version` が 1 で `window.until` がジョブの開始時刻以降。
- improve は有効な observe の後にだけ走る。

それ以外（例: stack の終了コード 2、`PATH` に無い拡張が `skipped` に入る、拡張のクラッシュ、古い `latest.json`）は失敗で、ジョブは終了コード 2 で終わる。

## ファイル

| ファイル | 書く時 | 中身 |
|---|---|---|
| `last.json` | 有効な実行の後だけ、一時ファイルからの rename で置き換える | 2 つの結果を合わせた `cycle` オブジェクト 1 つ: `stage` は `cycle`、`status` はどちらかが `warn` なら `warn`、他は `pass`、`results` は observe、improve の順、`skipped` は空。提案の本文は `jq -r '.results[].context'` で読む |
| `last-error` | 失敗した実行で、一時ファイルからの rename で置き換える。有効な実行で消す | 1 行目に UTC の時刻（`YYYY-MM-DDTHH:MM:SSZ`）、2 行目に理由 |

失敗しても前回の `last.json` は残る。ラッパーを走らせるのはジョブだけなので、`last-error` があれば最新の実行が失敗したことを表し、時刻を比べる必要はない。

## statusline の表示

オーナーの対応が要るときだけ赤で出す。`pass` で新しく、`last-error` が無ければ何も出さない。

- `last.json` が無い: `last-error` があれば `cycle ✗`、Home Manager の `stack-cycle` の plist があれば `cycle never`（ジョブは入っているが有効な実行がまだ無い）、どちらも無ければ何も出さない（cycle を設定していない）。
- `.status` が空でない文字列でないか、`.results` が配列でない: `cycle ?`。
- `.status` が `pass` 以外: `cycle <status> <N>`。`N` は `.results` 全体の `findings` の件数で、変更の数ではない（observe は `replay-change` を最大 20 件しか並べず、総数は `context` にある）。
- `last-error` がある: `✗` を足す（表示中の結果は前回の有効な実行のもの）。
- `last.json` の mtime が 36 時間より古い: `stale <日数>d` を足す（`pass` なら単独で出す）。
