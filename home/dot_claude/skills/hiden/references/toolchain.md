# 道具立て

## 使うツールは dotfiles が決める

手元で使えるツールと版の方針の正本は dotfiles（shuymn/dotfiles）で、グローバルの mise 設定 `~/.config/mise/config.toml` と、Nix が入れる日常の CLI がそれに当たる。ツールを選ぶときは、まずそこに入っているものを使う。入っていないものは一次資料で最新の安定版を確かめて選び、採否と理由を報告する。

## リポジトリでツールを足すとき

- **リポジトリが mise を使っている（`mise.toml` がある）:** `mise.toml` にメジャーの範囲で書き（`node = "24"`）、`mise lock` で `mise.lock` を更新してコミットに含める。
- **mise を使っていない（古い個人のリポジトリ、仕事のリポジトリ）:** `mise.toml` を足さず、`mise.local.toml` に書いて `mise lock --local` で固定する。

## 新しい個人のリポジトリ

- **版の固定:** mise で行う（言語別の版ファイルは使わない）。`mise.toml` にメジャーの範囲、`mise.lock`（`locked = true`）で固定する。Renovate の mise マネージャは無効にし、日次の mise-update ワークフローが `mise lock --bump` で PR を作る。見本は shuymn/dotfiles の `.github/workflows/mise-update.yml`。
- **ローカルの検査:** lefthook から走らせる。security/gha ワークフローのツール（actionlint・ghalint・betterleaks など）も mise で固定し、CI とローカルで同じものを使う。
- **Actions:** SHA で固定する。
- **JS/TS:** lint と format は oxlint と oxfmt。Cloudflare Workers の型は、`wrangler types` の生成物をコミットせず、`@cloudflare/workers-types` を tsconfig の `types` に入れ、使う binding だけを手書きの `src/env.d.ts`（`declare namespace Cloudflare { interface Env {...} }`）で宣言する。

Why: オーナーの明示的な好みで、リポジトリ間で揃っていることを各ベンダーの推奨より優先する。

## Actions の GitHub App トークン

`actions/create-github-app-token` に `client-id: ${{ vars.APP_CLIENT_ID }}` と `private-key: ${{ secrets.APP_PRIVATE_KEY }}` を渡す。App はリポジトリごとに専用のものを、ワークフローが要する権限だけで入れる。`app-id`/`APP_ID` は使わない（create-github-app-token v3.2.0 で非推奨）。変数とシークレットはオーナーが登録するので、App に要る権限（例: PR を作るジョブなら Contents と Pull requests の write）を伝える。
