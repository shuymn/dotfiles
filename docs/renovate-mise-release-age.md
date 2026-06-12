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

## 対処（優先順）

1. **timestamp のある backend / datasource に変更**:
   GitHub releases にバイナリを公開している tool は
   `ghalint = "..."` → `"github:suzuki-shunsuke/ghalint" = "..."` のように
   `github:` backend を使う。インストール元も変わるため `mise install` で動作確認する。
2. **regex custom manager で別 datasource を参照**（インストール方法を変えずに、
   mise manager より適した datasource を使う場合や timestamp のない経路を回避する場合）:
   `.github/renovate-self-hosted.json` に regex custom manager を追加し、
   `packageRules` の "Disable timestamp-less mise lookups" ルールの
   `matchDepNames` に tool 名を追加して mise manager 側の検出を止める
   （mise manager の `packageName` はリポジトリ名になることがあるため
   `matchPackageNames` ではマッチしない）。
   既存例: `go`（golang-version）、`python`（python-version）、
   `claude`（npm: @anthropic-ai/claude-code）、`codex`（npm: @openai/codex）。
   automerge は datasource/manager 単位のルールに依存するため、必要なら
   "Automerge minor/patch for regex-managed mise tools" ルールにも追加する。

将来 Renovate に aqua registry datasource が実装されれば、一部の workaround は不要になる
可能性がある（[renovate#42251](https://github.com/renovatebot/renovate/discussions/42251)）。
