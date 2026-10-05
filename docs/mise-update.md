# mise ツールの自動更新

`home/dot_config/mise/config.toml` と `mise.lock` の自動更新は `.github/workflows/mise-update.yml` だけが行う。Renovate の mise manager は無効にしている。GitHub Actions と `flake.lock` は引き続き Renovate が更新する。

## 選定規則

毎日の定期実行（手動実行も可）で、`scripts/update-mise-tools.py` が `[tools]` の各ツールについて次を満たす最新版を選ぶ。

- `mise ls-remote --json --no-versions-host --strict-metadata` が返す版のうち、`1.2.3` / `v1.2.3` の数値形式で prerelease でないもの
- 現在の版と同じメジャー番号で、現在より新しいもの
- リリース時刻が分かり、1 日以上経過しているもの。日付だけの時刻はその日の終わりとして扱う

選ばれなかった新しい版は「Held back」として理由付きで job summary に出る。メジャー更新はここに出るだけなので、手で `config.toml` を書き換えて `mise lock` する。mise の `minimum_release_age` 設定は固定版や lock からの選択には効かないため、待機の判定には使っていない。

`core:go` は mise がリリース時刻を返さないので、Go module proxy の `golang.org/toolchain` の公開時刻で補う。時刻が取れないツールは更新しない。

## 信頼境界

| ジョブ | 実行するもの | 権限 |
| --- | --- | --- |
| generate | flake の mise、上流のインストーラ、`mise lock` | `contents: read`。出力と成果物は信頼しない |
| verify | `github.sha` の `scripts/verify-mise-lock-candidate.py` | `contents: read` |
| publish | `github.sha` の `scripts/gh-api-retry.sh` と GitHub API 呼び出し | maintainer App token（contents / pull-requests write） |

verify は、変更が既存ツールの版だけで、同じメジャー内の前進であり、lock が config と整合することを確かめる。PR のタイトルと本文もここで検証済みの値から作る。publish は verify が記録したハッシュと成果物を突き合わせてから token を発行し、mise・Nix・生成物を実行しない。

publish は候補内容のハッシュから `mise-update/<hash>` ブランチを作り、署名付きコミット（`createCommitOnBranch`）で PR を開いて auto-merge を有効にし、古い `mise-update/*` PR を閉じる。同じ内容の PR が開いていれば何もしない。閉じられた PR と同じ内容は再提案しない。既存ブランチを force-update することはない。

## 手作業でツールを追加・変更するとき

1. `config.toml` を編集し、`mise lock` で `mise.lock` を更新する。`scripts/check-mise-lock-consistency.sh` で整合を確認できる。
2. `make check-mise-updates` を実行する。全ツールのリリース時刻が取れることを確認し、保留中の更新を一覧する。時刻が一つも取れないツールがあるとエラーになるので、時刻を返す backend（`github:`、`aqua:`、`npm:` など）に切り替える。
