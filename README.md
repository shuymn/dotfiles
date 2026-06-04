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

`make` ターゲットは bootstrap 用の薄い wrapper です。Nix 系ターゲットは評価前に `nix/local.nix.tmpl` から ignored な `nix/local.nix` を生成します。

`install.sh` は local checkout から `make apply` を実行するための補助 wrapper です。Nix のインストール、nix-darwin activation、remote `curl | sh` 実行には対応していません。完全な bootstrap には上の手順を使います。

最初の `make apply NIX_ROLE=personal` は `.chezmoi.toml.tmpl` から `~/.config/chezmoi/chezmoi.toml` を生成し、この checkout を `sourceDir` として設定し、選択した `nixRole` を chezmoi data に保存してから dotfiles を適用します。利用できる role は `nix/roles/` 配下のファイルです。その後は、通常の `chezmoi diff`、`chezmoi apply`、`chezmoi managed` がこのリポジトリを参照します。

chezmoi の暗号化には age を使います。既存の暗号化ファイルを復号する場合は、別管理で backup している `~/.config/age/key.txt` を復元します。新しい local identity を作る場合は `make age-key` を使います。key が存在する場合、`.chezmoi.toml.tmpl` は `scripts/age-recipient.sh` 経由で公開 recipient を導出します。age の秘密鍵は chezmoi と git の管理対象外です。

Nix / Home Manager の activation は nix-darwin 経由に一本化しています。`make switch` は activation 前に local Nix config を再生成します。このリポジトリでは standalone の `home-manager switch` flow は使いません。

nix-darwin activation が既存の `/etc/bashrc` または `/etc/zshrc` を報告した場合は、backup してから再実行します。

```bash
sudo mv /etc/bashrc /etc/bashrc.before-nix-darwin
sudo mv /etc/zshrc /etc/zshrc.before-nix-darwin
make switch
```

## よく使うコマンド

普段は次のコマンドだけを使います。

| コマンド | 用途 |
| --- | --- |
| `make check` | `nix/local.nix` を再生成し、ownership check と Nix flake check を実行します。 |
| `make build` | nix-darwin profile を build します。activation はしません。 |
| `make switch` | `nix/local.nix` を再生成し、nix-darwin と Home Manager を適用します。 |
| `chezmoi diff` | dotfile の未適用差分を確認します。 |
| `chezmoi apply` | dotfile を live home directory に適用します。 |
| `mise install` | mise-managed runtime / helper tools を install します。 |

## 状況別コマンド

次のコマンドは、上の主要コマンドが内部で呼ぶ部品、または特定の確認をしたいときの補助です。

| コマンド | 用途 |
| --- | --- |
| `make local` | chezmoi data から ignored な `nix/local.nix` を再生成します。 |
| `make chezmoi-config NIX_ROLE=personal` | このマシンの role を設定または更新します。 |
| `make age-key` | local age identity を作成し、chezmoi config を更新します。 |
| `make check-brew` | nix-darwin が生成する Brewfile と Homebrew 状態を確認します。 |
| `make check-ownership` | Home Manager が dotfile target を管理していないことを確認します。 |
| `make audit-cli-path` | PATH 上の non-Nix / non-mise owner と shadow を分類します。 |
| `make agents` | agent dotfiles を適用し、runtime sync を実行します。 |
| `chezmoi managed` | chezmoi が管理している target を一覧します。 |

## 所有モデル

- Nix / Home Manager: 日常的な CLI、shell-owned user packages、`mise`。共通 package は `nix/profiles/common.nix`、任意 group は `nix/profiles/*.nix`、role composition は `nix/roles/*.nix` にあります。
- nix-darwin: macOS 設定、Nix daemon/client 設定、shell 有効化、Homebrew taps、tap-only formulae、GUI casks。
- Nix host config: ignored な `nix/local.nix` を `nix/local.nix.tmpl` から生成します。tracked な `nix/local.default.nix` は generic fallback です。
- mise: 言語 runtime と pinned helper CLI。設定は `.config/mise/config.toml` と `.config/mise/mise.lock` です。
- chezmoi: `home/` 配下の tracked dotfiles。`~/.config` 配下の application config も通常の chezmoi source state として管理します。
- age: chezmoi encryption 用の local identity は `~/.config/age/key.txt` に置きます。これは tracking せず、別経路で backup します。

1つの target path には1つの writer だけを持たせます。このリポジトリでは、Home Manager は package group、profile composition、Home Manager 有効化、shell-owned package availability などの環境宣言層です。chezmoi は `$HOME` に現れるファイルを配置する層で、`~/.config` 配下の application config も含みます。

`home/**` 配下の target は、現状では Home Manager file module ではなく chezmoi が管理しています。target を Home Manager に移す場合は、対応する chezmoi source を同じ変更で削除または ignore し、この section も更新します。

Nix client 設定は `nix/darwin.nix` の `nix.settings` にあります。通常の flake behavior 用に separate な `home/dot_config/nix/nix.conf` はありません。

Git は shared behavior と local identity を分けています。共通設定は `home/dot_gitconfig`、identity、signing key、allowed signers、machine-specific CLI state は ignored な `~/.config/git/` 配下です。tracked config の最後で `~/.config/git/config.local` を include するため、local value は shared default を override できます。

Homebrew は nixpkgs にない GUI casks と tap-only formulae に限定しています。Homebrew の reconciliation は nix-darwin activation 経由だけで、このリポジトリには parallel Brewfile はありません。

Zed も同じ分離に従います。GUI app は `nix/darwin.nix` の Homebrew cask、settings と keymap は `home/dot_config/zed/**`、`nixd` や `nixfmt` など editor-facing tools は Nix / Home Manager です。Zed は `direnv` を読み込み、project flake / dev shell が project-local toolchain を提供できます。Zed extensions は chezmoi が `nixRole` から render し、`personal` は full interactive extension set、それ以外の role は minimal Nix extension set になります。

日常的な interactive CLI と editor-facing development tools は Nix / Home Manager に置きます。version-switched runtimes と pinned helper CLIs は mise に置きます。mise backend が separate global aqua、npm、pipx、cargo、uv tool layer を置き換えます。

global `cargo install`、`npm install -g`、`pipx install`、`uv tool install` はこのリポジトリの managed CLI layer ではありません。versioned global tools は mise backend、repo-specific tools は project-local environment に置きます。

既存の mise `npm:` / `pipx:` global tools は現時点では残しています。これらの backend で新しい tool を追加する場合は、明示的な理由が必要です。

`~/.config` は通常の directory です。application state と generated files は git の外に置き、意図した dotfiles だけを `home/dot_config/**` で管理します。

chezmoi source state は `.chezmoiroot` により `home/` 配下にあります。managed home files は repo root への symlink ではなく、この source state に置きます。

## Agent ファイル

静的な Claude、Codex、pi agent dotfiles は、chezmoi により `home/dot_claude/**`、`home/dot_codex/**`、`home/dot_pi/**` で管理します。`~/.codex/AGENTS.md` と `~/.pi/agent/AGENTS.md` は、`~/.claude/CLAUDE.md` への chezmoi-managed symlink です。

repo-owned skills は `etc/claude/skills/**` にあります。`skills` CLI は mise の `npm:skills` で pin しています。runtime install は additive なので、system、plugin、ad-hoc skills と共存できます。

`make agents` は agent dotfile targets を適用し、`etc/claude/skills/**` の全 skill を install し、local pi extensions checkout が存在する場合は `pi install` も実行します。

# ライセンス

MIT
