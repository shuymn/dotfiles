# GitHub App の作成（manifest）

App は manifest から作る。権限を伝えてオーナーに手で作らせない。

1. リポジトリの外の作業用の場所（セッションの scratchpad など）に、`manifest.json` と、それを GitHub に送る `create-app.html` を作る。
   - `manifest.json`: `name` は `shuymn-<repo>-ci`、`url` と `redirect_url` はリポジトリの URL、`public: false`、`hook_attributes` は `{"url": <リポジトリの URL>, "active": false}`、`default_events: []`、`default_permissions` はワークフローが要るものだけ（例: PR を作るジョブなら `contents` と `pull_requests` の `write`）。
   - `create-app.html`: manifest を値にした hidden の `manifest` フィールドを持ち、`https://github.com/settings/apps/new?state=<識別子>` に POST するフォーム 1 つ。
2. オーナーに HTML を開いて作成を確定してもらい、移動先の URL にある `code`（1 時間有効）を貼ってもらう。
3. `POST /app-manifests/{code}/conversions` で App の情報と秘密鍵に交換し、リポジトリの変数 `APP_CLIENT_ID`（`client_id`）とシークレット `APP_PRIVATE_KEY`（`pem`）に登録する。秘密鍵は画面にもファイルにも出さず、受け取った値をそのまま `gh secret set` に渡す。
4. App のインストール（`https://github.com/apps/<slug>/installations/new` で「Only select repositories」にそのリポジトリだけ）をオーナーに頼む。

Why: 権限と名前が manifest に残るので、手で作る設定のぶれが出ない。
