# dotfiles

自分の Mac を同じ環境にそろえて維持するための dotfiles。役割の違う 3 つの道具で構成する。

- **nix-darwin / Home Manager**: macOS の設定、Nix の設定、CLI、Homebrew の GUI アプリ
- **chezmoi**: `$HOME` に置く設定ファイル
- **mise**: 言語ランタイムと、版を追いかけたい CLI

## 新しい Mac を準備する

```bash
git clone https://github.com/shuymn/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
make install-nix
make host ROLE=personal
make converge
```

`make host` は、ユーザー名やホスト名などその Mac 固有の値とロールを、Git 管理外の `host.toml` に書き出す。Nix と chezmoi はどちらもこのファイルを読む。`ROLE` を省略すると `minimal` になる。

| ロール | 内容 |
| --- | --- |
| `minimal` | 共通設定のみ |
| `personal-lite` | 開発環境と、軽めの個人用アプリ |
| `personal` | `personal-lite` に、ウィンドウ管理（AeroSpace）、ローカル LLM、個人用アプリを加えたもの |
| `work` | 開発環境、ウィンドウ管理、ローカル LLM、仕事用のアプリと CLI |

各ロールの組み合わせは `nix/roles.toml` にある。

`make converge` は、chezmoi で設定ファイルを置き、nix-darwin を適用し、mise のツールを入れる。途中で止まったら原因を直して再実行すればよい。初回の nix-darwin 適用が既存の `/etc/bashrc` や `/etc/zshrc` を理由に止まったときは、退避してから再実行する。

```bash
sudo mv /etc/bashrc /etc/bashrc.before-nix-darwin
sudo mv /etc/zshrc /etc/zshrc.before-nix-darwin
make converge
```

chezmoi の暗号化には age を使う。鍵はリポジトリに入れず、別にバックアップしておく。新しく鍵を作るときは `make age-key` を使う。

## 日常の操作

| やりたいこと | コマンド |
| --- | --- |
| リポジトリの変更を Mac に反映する | `make converge` |
| 設定ファイルだけ反映する / 差分を見る | `chezmoi apply` / `chezmoi diff` |
| Nix の変更だけ反映する | `make switch` |
| 宣言と Mac の差を確かめる（変更しない） | `make doctor` |
| 変更を検証する | `make check` |
| ロールを変える | `host.toml` の `role` を書き換えて `make converge` |

ほかのターゲットは `make help` で確認できる。Home Manager は nix-darwin 経由で適用するので、`home-manager switch` は使わない。

## どこに何を書くか

1 つのファイルやパッケージの管理元は 1 つだけにする。

| 追加したいもの | 書く場所 |
| --- | --- |
| macOS の設定、Nix の設定 | `nix/darwin/profiles/common.nix` |
| GUI アプリ（Homebrew cask） | `nix/darwin/profiles/<プロファイル>.nix` |
| 日常的に使う CLI | `nix/home/profiles/<プロファイル>.nix` |
| 言語ランタイム、頻繁に更新したい CLI | `home/dot_config/mise/config.toml`（メジャー番号の範囲で書き、`mise lock` で lock を更新） |
| 設定ファイル | `home/` 以下（chezmoi のソース） |
| その Mac 固有の値、鍵、認証情報 | `host.toml` や各ツールのローカル設定（リポジトリには入れない） |

- Homebrew は宣言にない cask や formula が入っていると `make switch` が止まる。手で入れたものは宣言に足すか、アンインストールする。
- Home Manager が書いてよいファイルは `nix/ownership.nix` に列挙している。`make check` は全ロールについて、これ以外のファイルを書いていないか、chezmoi の管理対象と重なっていないかを検査する。

## 更新の仕組み

- **mise のツール**: `mise-update` ワークフローが毎日、範囲内の新しい版で `mise.lock` を更新する PR を作り、自動でマージする。メジャー更新は手で範囲を書き換える。詳しくは [docs/mise-update.md](docs/mise-update.md)。
- **`flake.lock` と GitHub Actions**: Renovate が PR を作る。lock の更新と minor / patch は自動でマージされ、メジャー更新は手でマージする。Capsule などの flake input もこの経路で上がる。
- **Homebrew の cask**: `make switch` では更新しない。各アプリの自動更新か `brew upgrade --cask` に任せる。
- **自動マージ**: main への必須チェックは `automerge-gate/all-passed` の 1 つだけ。PR で Enable auto-merge を押すと、ほかのチェックがすべて通った時点でマージされる。
