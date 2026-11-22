# GitHub App の作成（manifest）

App は manifest から作る。権限を伝えてオーナーに手で作らせない。

1. リポジトリの外の作業用の場所（セッションの scratchpad など）に、`manifest.json` と、それを GitHub に送る `create-app.html` を作る。
   - `manifest.json`: `name` は `<repo>-maintainer`、`url` と `redirect_url` はリポジトリの URL、`public: false`、`hook_attributes` は `{"url": <リポジトリの URL>, "active": false}`、`default_events: []`、`default_permissions` はワークフローが要るものだけ（例: PR を作るジョブなら `contents` と `pull_requests` の `write`）。
   - `create-app.html`: manifest を値にした hidden の `manifest` フィールドを持ち、`https://github.com/settings/apps/new?state=<識別子>` に POST するフォーム 1 つ。
2. オーナーに HTML を開いて作成を確定してもらい、移動先の URL にある `code`（1 時間有効）を貼ってもらう。
3. `POST /app-manifests/{code}/conversions` で App の情報と秘密鍵に交換し、リポジトリの変数 `APP_CLIENT_ID`（`client_id`）とシークレット `APP_PRIVATE_KEY`（`pem`）に登録する。秘密鍵は画面にもファイルにも出さず、受け取った値をそのまま `gh secret set` に渡す。`code` は一度しか交換できないので、応答は 1 本のパイプで 1 つのプログラムに渡し、その中で JSON を解析して両方を登録する（例: `gh api -X POST app-manifests/<code>/conversions | uv run python -I -c '…json.load(sys.stdin)…subprocess.run(["gh","secret","set",…],input=pem)…'`）。シェル変数と `echo` は通さない。Why: zsh の `echo` は `\n` を改行に変えるので、`pem` を含む JSON が壊れて解析できず、交換済みの `code` では取り直せない（秘密鍵は App の設定画面で作り直すしかない）。
4. App のインストール（`https://github.com/apps/<slug>/installations/new` で「Only select repositories」にそのリポジトリだけ）をオーナーに頼む。

Why: 権限と名前が manifest に残るので、手で作る設定のぶれが出ない。
