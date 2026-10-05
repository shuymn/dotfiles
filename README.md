# dotfiles

個人用の dotfiles。chezmoi でホームディレクトリのファイルを配置し、nix-darwin / Home Manager で macOS とユーザー環境を宣言する。

## インストール

```bash
git clone https://github.com/shuymn/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
make install-nix
make host ROLE=personal # personal 環境にする場合。未指定時は minimal
make converge
```

`make` ターゲットは初期セットアップ用の薄いラッパー。利用できるターゲットは `make help` または `Makefile` で確認する。

ユーザー名やホスト名などホスト固有の値とロールは、`make host` が作る Git 管理外の `host.toml` に置き、Nix と chezmoi の両方がここを読む。ロールを変えるときは `host.toml` を編集して `make converge` を実行する。

`make converge` は chezmoi 設定の生成と dotfiles の適用、nix-darwin の適用、mise のインストールをこの順に行う。途中で失敗したら原因を直して再実行する。その後は通常の `chezmoi diff` / `chezmoi apply` がこのリポジトリを参照する。

chezmoi の暗号化には age を使う。秘密鍵はローカル限定で、chezmoi と git の管理対象外。既存の暗号化ファイルを復号する場合は別管理のバックアップから復元し、新しいローカル鍵を作る場合は `make age-key` を使う。

Nix / Home Manager の適用処理は nix-darwin 経由に一本化している。普段は `make switch` を使い、単体実行の `home-manager switch` は使わない。

nix-darwin の適用処理が既存の `/etc/bashrc` または `/etc/zshrc` を報告した場合は、バックアップしてから再実行する。

```bash
sudo mv /etc/bashrc /etc/bashrc.before-nix-darwin
sudo mv /etc/zshrc /etc/zshrc.before-nix-darwin
make switch
```

## よく使うコマンド

普段使う入口は次の通り。詳細なターゲット一覧は `make help` で確認する。

| コマンド | 用途 |
| --- | --- |
| `make check` | 変更後の基本検証 |
| `make converge` | chezmoi・nix-darwin・mise をまとめて適用する |
| `make doctor` | 宣言と実機の差分を変更せずに報告する |
| `make build` | 適用せずに Nix プロファイルをビルドする |
| `make switch` | nix-darwin と Home Manager を適用する |
| `chezmoi diff` | dotfile の未適用差分を確認する |
| `chezmoi apply` | dotfile を実際のホームディレクトリに適用する |
| `mise install` | mise 管理の実行環境と補助ツールをインストールする |

## Capsule

Capsule は公式 flake を Home Manager 経由で導入する。デフォルトブランチを追い、Renovate の lockfile maintenance で更新する。実際のコミットは `flake.lock` に固定される。設定と zsh 初期化は chezmoi が管理し、共有 daemon は使わない。ランタイムは PATH 上のバージョンを表示し、mise のプロジェクト設定で解決されたバージョンと異なる場合だけ `(expected …)` を追加する。グローバル設定のみの場合や比較値を取得できない場合は追加表示しない。

旧 daemon 版からの更新は、バイナリ・設定・LaunchAgent をバックアップしてから、[公式の移行手順](https://github.com/shuymn/capsule/blob/v1.0.0/docs/migration.md)に従って旧 CLI で daemon を解除する。`cleanup = "check"` が適用を止めないよう、Homebrew 版と不要になった `shuymn/tap` を先に削除する。その後、`make switch` と `chezmoi apply ~/.config/capsule/config.toml` でバイナリと schema v2 設定を適用し、新しいシェルを起動する。

## 所有モデル

1つの対象パスには1つの管理元だけを持たせる。

- nix-darwin / Home Manager は環境宣言層。macOS 設定、Nix 設定、パッケージの利用可否、Homebrew 経由の GUI アプリなどを持つ
- Nix モジュールは `nix/home/**` と `nix/darwin/**` に分け、ロールごとのプロファイルの組み合わせは `nix/roles.toml` に一か所で書く。chezmoi も同じ表を読む
- Home Manager が書いてよいファイルは `nix/ownership.nix` に列挙し、`make check` が全ロールで検査する
- chezmoi は `$HOME` に現れる dotfile の配置層。Home Manager の file モジュールと同じ対象パスを二重管理しない
- mise はバージョン切り替え対象の実行環境と、バージョン固定した補助 CLI を持つ。リポジトリ固有のツールはプロジェクトローカルの環境に置く。更新は `mise-update` ワークフローが毎日行う（[docs/mise-update.md](docs/mise-update.md)）
- ホスト ID、署名鍵、age 鍵、マシン固有の状態はローカル限定
