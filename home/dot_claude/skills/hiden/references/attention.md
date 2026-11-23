# 注意の項目とキット

## 注意の項目

- 注意の項目は、フックや lint、テスト、それを通らないと進めないスクリプトが強制していない規則。キットの `attention/items.json` に役割を付けて書く。stack がコンテキストへ戻すのは `orchestrator` と全役割の `all` だけで、worker と reviewer の項目は指示書とレビュー依頼に手で貼る。
- 新しい規則は、仕組み、条件付きのルールブロック（当たるときだけ読む）、委任、常時の項目の順に検討する。常時の項目は、その役割が毎回守る必要のある規則だけにする。繰り返す失敗は、文を足す理由ではなく仕組みにする理由にする。
- 委任: 判断は自分でし、作業と監査は、指示書と報告を読む費用に見合うときだけ渡す。監査（steward）は読むだけで、依頼文に `Follow the body of ~/.claude/agents/steward.md.` とキットのディレクトリを渡し、フェーズの終わり、状態が古いとき、引き継ぎの前、振り返りで頼む。実行は [review.md](review.md) の「実行」の `agy-run` で行い、エラー（例: クォータ枯渇）で失敗したら [review.md](review.md) の「実行後の確認」を済ませてからオーケストレーターと同じモデル・労力にフォールバックする。`stack pr merge` の後に `audit due (…): run steward on kit <slug>` が出たら、その `<slug>` のキットのディレクトリを `shuymn/stack` の `docs/design/core-stages.md` §4.7「The due line」（行の意味もここ）のとおりに求め、費用の見積もりはせずに必ず、そのディレクトリだけを足した同じ書式で（自分の結論は添えない）steward をバックグラウンドで起動し、待たずに次の作業へ進む。ディレクトリが決まらなければ起動せず、slug を未解決として報告する。`agy-run` でバックグラウンド監査を走らせる間は、結果を読むまで同じ作業ツリーで編集しない（次の作業は別 worktree で進めるか読み取りだけにする）。見落としは台帳に記録する。
- 指示書の書き方は [subagent-brief.md](subagent-brief.md)。worker の常時の項目は `opus-worker.md` にあり、compaction の後はフックが worker のコンテキストへ戻す。

## キット

compaction の要約では目的、決定、進行中のものが落ちる。本質はキットに置き、フックがコンテキストへ戻す。委任の前にキットを作る。

- キットは、設定の `[kit].root` の下の `<名前>/`（`shuymn/stack` の `docs/design/phase2-core.md` §2.1）。`stack kit open <名前>` で作るか開き、そのセッションに結び付ける（外すのは `stack kit close <名前>`）。cwd からは探さないので、引き継いだセッションも開き直す。
- `state.md`（`NORTH.md` でもよい。先頭に本質: 目的、完了条件、クリティカルパス、オーナーの指示と決定、制約。続けて進行中、次の一手、未決。現在の状態のうち後の判断が依存するものだけを書き、委任・完了・マージ・オーナーの決定のたびに直す）。
- `attention/items.json` の形は `shuymn/stack` の `docs/design/phase2-core.md` §4.1.1「Attention items」。キットを作るときと開いたときに、役割 `orchestrator` で次の rule の項目が無ければ先頭に足す: `compaction の後は、進行中のステップの hiden reference を読み直してから続ける`。
- worker が複数なら、状態を出す `bin/board` を置いてもよい（任意。stack が実行して出力を戻す。`shuymn/stack` の `docs/design/phase2-core.md` §4.1.1）。
- `briefs/` と `reviews/` は、指示書、レビュー依頼、PR の文を置く任意の置き場で、stack は読まない。
- `stack kit open` と compaction の後に stack が開いたキットの状態、項目、board、引き継ぎの手順をコンテキストへ入れる（要約より正）。どの場面で何が入るかは `shuymn/stack` の `docs/design/phase2-core.md` §4.2 step 7。
- 引き継ぎ: 非常に長いセッションでは、尋ねずに新しいセッションへ引き継ぐのがオーナーの常設の依頼。環境に手段があるときだけ、`stack kit open` と compaction の後に出る手順で行う。子セッションは起動元のセッションにしか報告できないので、実行中またはフォローアップ予定の子セッションが無いフェーズの終わりで、`state.md` を直してから、リポジトリのルート（worktree なし）で「`stack kit open <名前>` を実行して続ける」として起動し、立ち上がったのを確かめて止まる。新しいセッションは `<orchestration-state>` を確かめ（無ければ止まる）、PR の待ちを置き直す。
