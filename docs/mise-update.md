# mise ツールの更新

`home/dot_config/mise/config.toml` の `[tools]` は各ツールのメジャー番号だけを範囲として書き（例: `node = "24"`）、正確なバージョンは `mise.lock` が固定する。各 Mac では `make mise` が lock どおりのバージョンを入れる。

## 自動更新の仕組み

`.github/workflows/mise-update.yml` が毎日（手動実行も可）`mise lock --bump` を実行し、範囲内の最新バージョンで `mise.lock` を解決し直す。変化があれば `mise-update` ブランチから PR を開き、auto-merge を有効にする。Renovate の mise manager は使わない。GitHub Actions と `flake.lock` は引き続き Renovate が更新する。

- バージョンの選び方は mise に任せる。config の `minimum_release_age = "1d"` により、公開から 1 日経っていないバージョンは選ばれない。
- `mise lock --bump` はメタデータを読んで lock を書くだけで、ツールをインストールも実行もしない。そのため同じジョブで maintainer App token を作って PR を開く。
- バージョンが変わるツールだけを lock し直す。バージョンが変わらないツールの checksum や URL は書き換えないので、配布物の差し替えが自動マージされることはない。
- 解決し直しなので、新しいバージョンが取り下げられたときなどにバージョンが下がることもある。PR 本文の表で確認できる。

### ブランチと PR の扱い

`mise-update` ブランチがすでに残っているときは、lock の一致と `main` への追従状態で次のように分岐する。

- **同じ lock で PR が閉じている:** 却下として何もしない。
- **同じ lock で実行開始時の `main` に追いついている:** ブランチを再利用し、PR が開いていればラベルと auto-merge を確かめ、PR がない（前回の実行が PR 作成前に失敗した）ときは新しく開く。
- **lock が変わった、または `main` に遅れている:** 古い base のチェックや lock 行の衝突を避けるため、開いていた PR を閉じてブランチを作り直す。

### CI による検証

`.github/workflows/mise-lock.yml` が、mise の設定か lock を変える PR に対して macOS（`macos-arm64` の配布物）で検証する（`linux-x64` の配布物は確かめない）。

- `mise install --locked` ですべてのツールを入れ、lock が変わったツールを起動する（`config.toml` かワークフロー自体が変わったときは全ツールを起動する）。
- 起動は配置された実行ファイルに対して行い、デフォルトは `--version`、別の名前や引数が要るツールはワークフロー内の表に従う。
- `automerge-gate` がこの結果を待つため、インストールや起動に失敗するバージョンは自動マージされない。

## 手作業での変更

- ツールの追加・変更は config にメジャー番号の範囲で書き、`home/dot_config/mise` で `mise lock` を実行して lock を更新する。
- 自動更新から外すツールは config に正確なバージョンを書き（例: `"0.38.0"`）、理由をコメントに残す。`mise lock --bump` はそのバージョンから動かさない。
- メジャー更新は自動では入らない。`mise outdated --bump` で確認し、config の範囲を書き換えて `mise lock` する。
