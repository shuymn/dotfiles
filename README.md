# dotfiles

自分の Mac を再現・維持するための個人用 dotfiles（他環境向けの汎用テンプレートではない）。役割の異なる 3 つのツールで構成する。

- **nix-darwin / Home Manager**: macOS の設定、Nix の設定、日常利用する CLI、Homebrew の GUI アプリ
- **chezmoi**: `$HOME` に配置する設定ファイル
- **mise**: 開発用の言語ランタイムと、新しいバージョンを追いかけたい CLI

## 新しい Mac のセットアップ

```bash
git clone https://github.com/shuymn/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
make install-nix
make host ROLE=personal
make converge
```

- `make host` はユーザー名やホスト名などの固有値とロール（デフォルトは `minimal`）を Git 管理外の `host.toml` に書き出す。ロールとプロファイルの組み合わせは [nix/roles.toml](nix/roles.toml) にある。
- `make converge` は chezmoi・nix-darwin・mise・エージェント関連のセットアップを順に適用する。途中で止まっても原因を直して再実行できる（初回の nix-darwin 適用が既存の `/etc/bashrc` や `/etc/zshrc` で止まった場合は退避してから再実行する）。
- chezmoi の暗号化には age を使う。鍵はリポジトリに入れず、別にバックアップしておく（新規作成は `make age-key`）。

## 日常の操作

| やりたいこと | コマンド |
| --- | --- |
| リポジトリの変更を Mac に反映する | `make converge` |
| 設定ファイルだけの差分確認 / 反映 | `make diff` / `chezmoi apply` |
| Nix / macOS 設定だけ反映する | `make switch` |
| 宣言と Mac の差を確認する（変更しない） | `make doctor` |
| 構成と所有権の整合を検証する | `make check` |
| 全ターゲットの一覧を見る | `make help` |

Home Manager は nix-darwin 経由で適用するため、`home-manager switch` は使わない。

## 構成の正本

- **ロール・パッケージ構成**: [nix/roles.toml](nix/roles.toml) および `nix/` 以下
- **設定ファイル（chezmoi ソース）**: `home/` 以下
- **管理元の境界・保守ルール・自動更新の制約**: [AGENTS.md](AGENTS.md)
