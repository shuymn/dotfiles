# dotfiles

個人用の dotfiles リポジトリです。chezmoi でホームディレクトリのファイルを配置し、nix-darwin / Home Manager で macOS とユーザー環境を宣言します。

## インストール

```bash
git clone https://github.com/shuymn/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
make install-nix
make apply NIX_ROLE=personal
make switch
mise install
```

`make` ターゲットは bootstrap 用の薄い wrapper です。利用できる target は `make help` または `Makefile` で確認します。Nix 系ターゲットは評価前に ignored な local Nix config を生成します。

最初の `make apply NIX_ROLE=personal` は chezmoi config を生成し、この checkout を source にして dotfiles を適用します。その後は通常の `chezmoi diff` / `chezmoi apply` がこのリポジトリを参照します。

chezmoi の暗号化には age を使います。秘密鍵は local-only で、chezmoi と git の管理対象外です。既存の暗号化ファイルを復号する場合は別管理の backup から復元し、新しい local identity を作る場合は `make age-key` を使います。

Nix / Home Manager の activation は nix-darwin 経由に一本化しています。普段は `make switch` を使い、standalone の `home-manager switch` flow は使いません。

nix-darwin activation が既存の `/etc/bashrc` または `/etc/zshrc` を報告した場合は、backup してから再実行します。

```bash
sudo mv /etc/bashrc /etc/bashrc.before-nix-darwin
sudo mv /etc/zshrc /etc/zshrc.before-nix-darwin
make switch
```

## よく使うコマンド

詳細な target 一覧は `make help` を正本にします。普段の入口は次の通りです。

| コマンド | 用途 |
| --- | --- |
| `make check` | 変更後の基本検証。 |
| `make build` | activation せずに Nix profile を build します。 |
| `make switch` | nix-darwin と Home Manager を適用します。 |
| `chezmoi diff` | dotfile の未適用差分を確認します。 |
| `chezmoi apply` | dotfile を live home directory に適用します。 |
| `mise install` | mise-managed runtime / helper tools を install します。 |
| `make agents` | agent dotfiles と repo-owned skills を反映します。 |

## 所有モデル

1つの target path には1つの writer だけを持たせます。

- nix-darwin / Home Manager は環境宣言層です。macOS 設定、Nix 設定、package availability、Homebrew 経由の GUI app などを持ちます。
- Nix module は `nix/home/**` と `nix/darwin/**` に分け、どちらも `nix/local.nix` の同じ role 名で role module を選びます。
- chezmoi は `$HOME` に現れる dotfile の配置層です。Home Manager file module と同じ target を二重管理しません。
- mise は version-switched runtime と pinned helper CLI を持ちます。repo-specific tool は project-local environment に置きます。
- host identity、signing key、age key、machine-specific state は local-only です。

## Agent ファイル

静的な agent dotfiles は chezmoi source state に置きます。repo-owned skills は `etc/claude/skills/**` が source で、runtime への反映は `make agents` に寄せます。
