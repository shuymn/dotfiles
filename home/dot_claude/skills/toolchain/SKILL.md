---
name: toolchain
description: Adding or pinning a tool or version; setting up a repository's CI or GitHub Actions.
---

# ツールチェーン

## 使うツールは dotfiles が決める

手元で使えるツールとバージョン方針の正本は dotfiles（shuymn/dotfiles）で、グローバルの mise 設定 `~/.config/mise/config.toml` と、Nix が入れる日常の CLI がそれに当たる。ツールを選ぶときは、まずそこに入っているものを使う。入っていないものは一次資料で最新の安定バージョンを確かめて選び、採否と理由を報告する。

## リポジトリでツールを足すとき

- **リポジトリが mise を使っている（`mise.toml` がある）:** `mise.toml` にメジャーの範囲で書き（`node = "24"`）、`mise lock` で `mise.lock` を更新してコミットに含める。
- **mise を使っていない:** 別の手段（Nix flake の devShell など）で固定していればそこに足す。無ければ（古い個人のリポジトリ、仕事のリポジトリ）`mise.toml` を足さず、`mise.local.toml` に書いて `mise lock --local` で固定する。

## 新しい個人のリポジトリ

- **バージョンの固定:** mise で行い、`mise.toml` にメジャーの範囲を書き、`mise.lock`（`locked = true`）で固定する。言語別のバージョンファイルは使わない。例外は、外部のビルド環境が言語別のバージョンファイルしか読まないとき（`.node-version` など）で、その言語のバージョンはそのファイルだけに書き、mise には `idiomatic_version_file_enable_tools` で同じファイルを読ませる（`mise.lock` はそのまま固定する）。Renovate の同じファイルのマネージャ（`nodenv` など）は無効にする。Renovate の mise マネージャは無効にし、日次の mise-update ワークフローが `mise lock --bump` で PR を作る。見本は shuymn/dotfiles の `.github/workflows/mise-update.yml`。
- **デプロイ:** main は依存の更新が入り続けるので、main から直接デプロイしない。release-please のリリース PR をマージしたときだけ、ワークフローが `release` ブランチをタグへ fast-forward し、デプロイ先はそのブランチだけを見る。`release` を作る・進める・消すのはリリース用の App だけに rulesets で絞り、`release_immutability` を有効にする。
- **ローカルの検査:** lefthook から走らせる。security/gha ワークフローのツール（actionlint・ghalint・betterleaks など）も mise で固定し、CI とローカルで同じものを使う。
- **GitHub のリポジトリ設定:** マージ方式、rulesets、許可する Actions、セキュリティ機能は `.github/infra.yaml` に宣言し、gh-infra（`mise.toml` で固定）の `plan` で差分を見てから `apply` する。`gh api` で直接変えない。見本は shuymn/octo-translator の `.github/infra.yaml`。Why: API で直接変えると設定がリポジトリに残らず、標準とのずれも `plan` で見えなくなる。
- **JS/TS:** lint と format は oxlint と oxfmt。Cloudflare Workers の型は、`wrangler types` の生成物をコミットせず、`@cloudflare/workers-types` を tsconfig の `types` に入れ、使う binding だけを手書きの `src/env.d.ts`（`declare namespace Cloudflare { interface Env {...} }`）で宣言する。

Why: オーナーの明示的な好みで、リポジトリ間で揃っていることを各ベンダーの推奨より優先する。

## Actions の GitHub App トークン

`actions/create-github-app-token` に `client-id: ${{ vars.APP_CLIENT_ID }}` と `private-key: ${{ secrets.APP_PRIVATE_KEY }}` を渡す。`app-id`/`APP_ID` は使わない（create-github-app-token v3.2.0 で非推奨）。App はリポジトリごとに専用のものを、ワークフローが要する権限だけで、manifest から作る（手順は [github-app.md](references/github-app.md)）。
