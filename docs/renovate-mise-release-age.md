# Renovate × mise: minimumReleaseAge とタイムスタンプのないリリース

## 問題

このリポジトリの Renovate は `minimumReleaseAge` + `internalChecksFilter: "strict"`
で「リリースから一定期間経過した最新バージョン」へフォールバック更新する。
この仕組みは datasource が `releaseTimestamp` を返すことが前提で、Renovate 42 以降、
タイムスタンプのないリリースは **常に経過期間未達（pending）扱い** になる
（[Renovate 42 リリースノート](https://github.com/renovatebot/renovate/releases/tag/42.0.0)）。

mise manager では backend や tool の形によって datasource が変わる。
Renovate 43.212.4 では `github-tags` は timestamp を返すため安全だが、
`java-version` / `git-tags` / `git-refs` など timestamp のない datasource や、
Renovate が unsupported と判断する URL 形式に落ちる tool は Dependency Dashboard の
"Pending Status Checks" に最新バージョンが載ったまま **永久に PR が作られない**。

Renovate の解決の要点（`lib/modules/manager/mise/`）:

1. backend なしの short name は、まず mise/asdf の静的マッピング、次に mise registry を見る。
   registry は `github` backend があれば優先し、なければ登録順の backend を使う。
2. `core:` / `asdf:` / `aqua:` / `vfox:` のような registry 系 backend も、まず静的マッピングを見てから backend 固有の解決に落ちる。
   例: `aqua:act` は静的マッピングで `github-releases`、未知の `aqua:owner/repo` は `github-tags`。
3. backend によっては tool 名や version で datasource が分岐する。
   `cargo:https://...` は `tag:` なら `git-tags`、`branch:` / `rev:` なら `git-refs`。
   `pipx:git+...` の非 GitHub URL は `git-refs`。
   `spm:` の非 GitHub URL は Renovate では unsupported。
4. plain `pipx:` の PyPI package は通常 `pypi` datasource になるが、Renovate 43.212.4
   では `info.home_page = null` を返す package で JSON API parse → simple fallback が壊れ、
   `pipx:tavily-cli` と `pipx:microsandbox` は `no-result` になることがある。
   このリポジトリでは `custom.pypi-json` + regex custom manager に逃がし、mise manager
   側の lookup を disable して回避している。

## 検知

新しい tool を `home/dot_config/mise/config.toml` に追加したら:

```sh
make check-mise-renovate
```

`scripts/check-mise-renovate-age.sh` は `.github/workflows/renovate.yml` の
`renovate-version` と同じ Renovate ref を使い、top-level `[tools]` と
`tasks.*.tools` の解決経路を分類する。timestamp のない datasource、unsupported path、
または未分類の `WARN` があると非ゼロ終了する。regex custom manager で追跡し、
mise manager 側の lookup も disable 済みの tool は `OK` になる。

このリポジトリでは Renovate の mise native artifact update を
`skipArtifactsUpdate: true` で無効化し、Renovate は
`home/dot_config/mise/config.toml` の version bump だけを担当する。lockfile 更新は
Renovate の実行場所から分離した GitHub-native reconciler が所有する。
`.github/workflows/mise-lock-candidate.yml` は PR 上で read-only に動き、
`scripts/update-mise-lock-for-changed-tools.py` が変更された既存 tool だけに対して
`mise trust config.toml` →
`mise exec node -- env MISE_NPM_PACKAGE_MANAGER=npm mise lock --platform macos-arm64,linux-x64 <tool...>`
を実行して candidate artifact を作る。実行コードとNix定義は PR HEAD ではなく base SHA の分離
worktreeから読み、PR側からはversion-onlyと確認する `config.toml` だけをデータとして移す。
生成は `nix shell .#mise -c ...` でこの flake が公開する mise を使うため、
Home Manager が使う Nix 側の mise と CI の lockfile 生成用 mise は同じ `miseFor` 定義に従う。
regex custom manager だけで version を更新したケースや、一部 backend で
native artifact update が取りこぼすケースでも lockfile が stale のまま残らないようにしつつ、
Renovate に任意 command 実行権限を持たせない。この境界は self-hosted Renovate 固有ではないため、
Mend-hosted Renovate へ移行しても維持できる。

GitHub Ruleset の required status check は `automerge-gate/all-passed` だけにする。
`.github/workflows/automerge-gate.yml` は `pkgdeps/automerge-gate` の private mode で
PR 上の GitHub Actions check runs を集約し、Renovate が platform-native auto-merge を
有効化したタイミングで全チェックの完了を待って commit status を成功/失敗にする。
Ruleset に workflow/path-filtered job を個別列挙しないため、対象外 PR を
"Waiting for status to be reported" で止めず、新しい CI job を追加しても Ruleset 更新漏れで
automerge gate から外れにくい。この dotfiles repo では外部 fork PR を自動 merge 対象にしないため
private mode を使う。fork PR を受け付けて同じ gate に載せる運用へ変える場合は public mode へ
切り替える。

candidate workflow は mise config を更新する同一 repository の PR だけで macOS lock 更新を走らせる。
更新が必要なら artifact を保存していったん失敗し、次の PR head が改めて全チェックを通るまで
`automerge-gate/all-passed` を成功させない。`.github/workflows/mise-lock-reconcile.yml` は
`workflow_run` で default branch の信頼済みコードとして起動し、PR metadata、base/head SHA、
version-only config diff、candidate の対象 lock section、TOML、platform、SHA-256 を再検証する。
検証後にだけ `MISE_LOCK_APP_CLIENT_ID` と `MISE_LOCK_APP_PRIVATE_KEY` から repository-scoped の
短命 GitHub App token を作り、Git Data API で `home/dot_config/mise/mise.lock` だけを commit する。
ref 更新は non-force なので、検証後に Renovate が branch を更新した場合は失敗して次の run に任せる。
privileged job は PR の checkout、Nix、mise、PR 内 script を実行しない。

lock maintainer App はこの repository の Contents read/write だけを持たせ、Renovate App と共有しない。
App token の push は新しい `pull_request.synchronize` を発火し、candidate workflow、通常 CI、
automerge gate が新しい HEAD を検証する。reconciler は PR ごとの autofix 回数を記録せず HEAD 単位で
冪等に動くため、Renovate が branch を force-update して過去の lock commit を除いても再収束する。

初期設定では webhook を無効にした専用 GitHub App を作り、Repository permissions は
`Contents: Read and write` だけにして `shuymn/dotfiles` のみに install する。App の Client ID を
repository variable `MISE_LOCK_APP_CLIENT_ID`、生成した private key 全文を repository secret
`MISE_LOCK_APP_PRIVATE_KEY` に保存する。workflow は token 発行時にも `permission-contents: write` を
明示し、現在の repository だけへ scope を狭める。

`mise lock` 後は `scripts/check-mise-lock-consistency.sh` で top-level `[tools]` の
config version と lockfile version が一致していることも確認する。mise.lock では
一部の `github:` tool の先頭 `v` が正規化で落ちるため、この検証では先頭 `v` の有無だけは
同一バージョンとして扱う。`http:` かつ config に `url` を持つ tool については、
configured `lockfile_platforms` の platform URL が lockfile に残っていることと、
lockfile に保存された options が config の options と一致することも検証する。

さらに `scripts/update-mise-lock-for-changed-tools.py` が base の `mise.lock` と比較し、
変更対象 tool 以外の lock section、preamble、生成ファイルが変わった場合は失敗する。
既存 tool の version-only change だけを自動 lock 更新の対象にし、tool 追加・削除や
`url` / `bin` / settings 変更は手動で lockfile を更新して確認する。

`http:cursor-agent` は意図的に `strip_components` を指定しない。Cursor の archive は
`strip_components` なしでも `cursor-agent` を実行できる一方、Renovate コンテナの
`mise 2026.6.14` が生成した `strip_components` 付き lock entry は、Nix 側の
`mise 2026.5.12` では locked install 時に別 entry として扱われて失敗した。config から
`strip_components` を外し、lockfile に options table を持たせない形なら、両方の mise で
同じ `http:cursor-agent` lock entry として扱われる。

## 対処（優先順）

1. **timestamp のある backend / datasource に変更**:
   GitHub releases にバイナリを公開している tool は
   `ghalint = "..."` → `"github:suzuki-shunsuke/ghalint" = "..."` のように
   `github:` backend を使う。インストール元も変わるため `mise install` で動作確認する。
2. **regex custom manager で別 datasource を参照**（インストール方法を変えずに、
   mise manager より適した datasource を使う場合や timestamp のない経路を回避する場合）:
   `.github/renovate-self-hosted.json` に regex custom manager を追加し、
   `packageRules` の "Disable mise lookups tracked via regex managers" ルールの
   `matchDepNames` に tool 名を追加して mise manager 側の検出を止める
   （mise manager の `packageName` はリポジトリ名になることがあるため
   `matchPackageNames` ではマッチしない）。
   既存例: `go`（golang-version）、`python`（python-version）、
   `claude`（npm: @anthropic-ai/claude-code）、`codex`（npm: @openai/codex）、
   `tavily-cli` / `microsandbox`（custom.pypi-json; native pipx/pypi lookup workaround）。
   automerge は datasource/manager 単位のルールに依存するため、必要なら
   "Automerge minor/patch for regex-managed mise tools" ルールにも追加する。

将来 Renovate に aqua registry datasource が実装されれば、一部の workaround は不要になる
可能性がある（[renovate#42251](https://github.com/renovatebot/renovate/discussions/42251)）。
