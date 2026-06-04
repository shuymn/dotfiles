# dotfiles

個人用の dotfiles。chezmoi でホームディレクトリのファイルを配置し、nix-darwin / Home Manager で macOS とユーザー環境を宣言する。

## インストール

```bash
git clone https://github.com/shuymn/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
make install-nix
make apply NIX_ROLE=personal
make switch
mise install
```

`make` ターゲットは初期セットアップ用の薄いラッパー。利用できるターゲットは `make help` または `Makefile` で確認する。Nix 系ターゲットは評価前に Git 管理外のローカル Nix 設定を生成する。

最初の `make apply NIX_ROLE=personal` は chezmoi 設定を生成し、このリポジトリを管理元にして dotfiles を適用する。その後は通常の `chezmoi diff` / `chezmoi apply` がこのリポジトリを参照する。

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
| `make build` | 適用せずに Nix プロファイルをビルドする |
| `make switch` | nix-darwin と Home Manager を適用する |
| `chezmoi diff` | dotfile の未適用差分を確認する |
| `chezmoi apply` | dotfile を実際のホームディレクトリに適用する |
| `mise install` | mise 管理の実行環境と補助ツールをインストールする |
| `make agents` | agent 用 dotfiles とリポジトリ管理の skills を反映する |

## 所有モデル

1つの対象パスには1つの管理元だけを持たせる。

- nix-darwin / Home Manager は環境宣言層。macOS 設定、Nix 設定、パッケージの利用可否、Homebrew 経由の GUI アプリなどを持つ
- Nix モジュールは `nix/home/**` と `nix/darwin/**` に分け、どちらも `nix/local.nix` の同じロール名でロールモジュールを選ぶ
- chezmoi は `$HOME` に現れる dotfile の配置層。Home Manager の file モジュールと同じ対象パスを二重管理しない
- mise はバージョン切り替え対象の実行環境と、バージョン固定した補助 CLI を持つ。リポジトリ固有のツールはプロジェクトローカルの環境に置く
- ホスト ID、署名鍵、age 鍵、マシン固有の状態はローカル限定

## Agent ファイル

静的な agent 用 dotfiles は chezmoi の管理元に置く。リポジトリ管理の skills は `etc/claude/skills/**` が管理元で、実行環境への反映は `make agents` に寄せる。
