# mise ツールの更新

`home/dot_config/mise/config.toml` の `[tools]` は各ツールのメジャー番号だけを範囲として書き（例: `node = "24"`）、正確な版は `mise.lock` が固定する。各 Mac では `make mise` が lock どおりの版を入れる。

## 自動更新

`.github/workflows/mise-update.yml` が毎日（手動実行も可）`mise lock --bump` を実行し、範囲内の最新版で `mise.lock` を解決し直す。変化があれば `mise-update` ブランチから PR を開き、auto-merge を有効にする。Renovate の mise manager は使わない。GitHub Actions と `flake.lock` は引き続き Renovate が更新する。

- 版の選び方は mise に任せる。config の `minimum_release_age = "1d"` により、公開から 1 日経っていない版は選ばれない。
- `mise lock --bump` はメタデータを読んで lock を書くだけで、ツールをインストールも実行もしない。そのため同じジョブで maintainer App token を作って PR を開く。
- 版が変わるツールだけを lock し直す。版が変わらないツールの checksum や URL は書き換えないので、配布物の差し替えが自動マージされることはない。
- 解決し直しなので、新しい版が取り下げられたときなどに版が下がることもある。PR 本文の表で確認できる。
- 同じ lock の PR が開いている（または閉じて却下した）ときは何もしない。内容が変わったときはブランチを作り直し、古い PR は閉じる。

## 手作業での変更

- ツールの追加・変更は config にメジャー番号の範囲で書き、`home/dot_config/mise` で `mise lock` を実行して lock を更新する。
- メジャー更新は自動では入らない。`mise outdated --bump` で確認し、config の範囲を書き換えて `mise lock` する。
