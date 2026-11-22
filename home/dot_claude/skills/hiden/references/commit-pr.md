# コミットと PR

コミットや PR にする変更は、次の順に進める。

1. **`commit`** スキルに言語のフラグ（`--english` か `--japanese`）を付ける。新しいブランチが要るときは `--branch` も付ける。
   - 整形は、リポジトリのスクリプトやフックが掛けるツールと範囲だけで行い、コミットの前に自分の変更に由来しない差分（hunk）がないか確かめる。
2. **公開の検査:** 公開リポジトリでは、各 push と各 `gh pr create`/`gh pr edit`（`create-pr --update` や CI の測定値の追記を含む）の直前に、送る題と本文の全文をファイルに書いて `stack-public check <PR の base>..<送る head> --title-file <題> --body-file <本文> --branch <ブランチ>` を通し、通したファイルをそのまま送る。`stack-public` が起動しないとき（例: 見つからない、実行できない）も、ヒットと同じく push と PR の作成・編集を止める。push は `stack-public check <base>..HEAD --branch <ブランチ> && git push …` の 1 コマンドで書き、検査を別の手順に分けない（PR 作成前の途中 push や CI 実行の push で検査が抜けるのを防ぐ）。base は PR の宛先（fork なら upstream）の実際の base にする。`--fill` 系でコミットの文を写すときも同じ範囲で通す。内容を変えたら通し直す。
   - 許可を得て内容を変えないつもりで履歴を書き換えたとき（例: fixup の autosquash）は、push の前に書き換え前の head と `git diff` でツリーが同じかを確かめる。
   - PR の作成・編集で `stack-public check` が通った後、`stack-jev-semantic` が `PATH` にあれば、送る head をコミットで固定し、`if mb=$(git merge-base <PR の base> <head>); then stack run outbound --ext jev-semantic --range "$mb..<head>" --title-file <題> --body-file <本文> --branch <ブランチ>; else echo "jev-semantic skipped: no merge base"; fi` を走らせる（`skipped` が出たら `jev-semantic` を省いたと報告する）。出た指摘（例: テストや検査を弱めた理由が本文に無い、差分が支えない主張）は、本文か差分で直すか直さない理由を付けて、どちらも報告する。結果は助言で、push も PR も止めない。
3. **`create-pr`** スキルに同じ言語のフラグを付け（base がデフォルトでなければ `--base=<base>` も）、draft で作る。
4. **レビュー:** PR の差分（PR が無ければ base との差分）に行う。担当と区分（設計書の保証・前提・受け入れる制限を変える差分を含む）は [review.md](review.md) の「実行」と「いつ」に従う。文書や設定だけの低区分の PR でも省かず、結果を台帳に 1 行書いてからマージを頼む。
5. **`simplify`:** コードを変える PR では、最後の Codex ラウンドの後に `origin/<base>...HEAD` に対して毎回行う。省けるのは文書・設定・テストだけか数行の変更で、省いたら理由を報告する。その後、本文を `create-pr --update` で直し `gh pr ready` にする。
6. **CI** が通るまで直す。
   - CI 成功の印だけでなく CI が出す測定値も読み（読み方は [verification.md](verification.md) の「性能の数値」）、PR 本文に `gh pr edit` で書く（コミットに書くと CI がやり直しになる）。
   - マージの出力に `audit due (…)` の行があれば、[attention.md](attention.md) の委任のとおり steward をバックグラウンドで起動する。
   - 共有の連番や生成値（例: lockfile、CHANGELOG、migration の番号）を変える PR が並ぶときは、マージの順を先に決め、先頭の PR だけが base を取り込んでマージし、次は新しい base で CI がパスしてから。Why: Git はこれらをテキストとしてマージするので、各 PR がパスしてもマージ結果は未検証。
7. **PR のレビューコメント**（AI のレビューを含む）の 1 件ずつに採否を決め、スレッドに返事を書いてからマージする。直したものは commit を、見送るものは理由を書く。resolve はしない（ruleset が要求するリポジトリではオーナーに確かめる）。
   - PR を作る依頼には、その PR の bot のスレッドへの返信も含まれる。triage-review の「明示的に頼まれたときだけ投稿する」は、PR を作る作業の外でレビューだけを頼まれたときの規則として読む。仕事のリポジトリではマージはチームなので、PR を渡す時点で返信を済ませる。
   - bot のスレッドへの返信は、投稿前に triage-review の `references/pr-replies.md` を読み、その書式に従う。

**言語の決め方:** 既存のコミット履歴の言語に揃える。履歴で決まらない新しいリポジトリでは、公開リポジトリ（OSS）か公開する予定のものは英語、それ以外は日本語。公開リポジトリは `public-text` スキルにも従う。非公開で公開の予定が分からなければ、オーナーに尋ねる。
