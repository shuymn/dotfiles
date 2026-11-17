# 注意の予算とキット

## 注意の予算

- 注意の項目は、フックや lint、テスト、それを通らないと進めないスクリプトが強制していない規則。役割（orchestrator、worker、reviewer）ごとの常時の項目数と、指示文のファイルの大きさの上限は `~/.claude/attention/budget.json` にあり、下げることしかできない。使用量は `attention-budget.py status`。
- 項目は、全セッション共通の `~/.claude/attention/items.json` と、キットの `attention/items.json` に書く（budget.json の registers に足すのは許される）。上限は共通とそのキットの合計にかかり、役割が `all` の項目は全役割に数える。
- 新しい規則は、仕組み、条件付きの束（当たるときだけ読む）、委譲、常時の項目の順に検討する。常時の項目に足せるのは空きがあるときだけ。上限なら既存の項目を仕組みか束にして外してから足す。オーナーの指示でも外す前には足さず、上限と入れ替えの案を示す。繰り返す失敗は、文を足す理由ではなく仕組みにする理由にする。
- 委譲: 判断は自分でし、作業と監査は、指示書と報告を読む費用に見合うときだけ子に渡す。監査は steward に、段の終わり、状態が古いとき、引き継ぎの前、振り返りで頼む。T3 Code では `delegate_task`（`interactionMode: "plan"`）に `Follow the body of ~/.claude/agents/steward.md.` とキットの場所を渡す。報告は 10 行以内、見落としは台帳に記録する。
- 指示書の書き方は [subagent-brief.md](subagent-brief.md)。worker の常時の項目は opus-worker.md にあり、`worker-signals.json` の `workers` に載せた worker にはフックが文脈へ戻す。reviewer の項目は依頼文に貼る。

## キット

要約はモデルが書くので目的、決定、進行中のものが落ちる。本質はキットに置き、フックが文脈へ戻す。委任の前にキットを作る。

- キットは `~/.claude/projects/<cwd の英数字以外を - にしたもの>/<名前>-orchestration/`、または `worker-signals.json` の `orchestrators` に載せた作業場所。cwd かその親から探す。`/tmp` やセッションの scratchpad には置かない。
- `state.md`（`NORTH.md` でもよい。先頭に本質: 目的、完了条件、経路、オーナーの指示と決定、制約。続けて進行中、次の一手、未決。現在の状態だけを 3000 バイト以内で書き、委任・完了・マージ・オーナーの決定のたびに直す）、`attention/items.json`、`watch`（状態を古くする更新のパスを 1 行ずつ: 台帳、`signals/seen`。検知できるのは一部）。worker が複数なら `units.json` と、状態を出す `bin/board` も置く。
- `orchestration-context.py` が、開始・再開・clear・compaction の後に、状態、項目、予算の使用量、マクロの問い、board を文脈へ入れる（要約ではなくこれが正）。`watch` の印が状態より新しければ、フックがターンの終わりを 1 度止める（状態を直す。変化が無ければ touch）。
- 引き継ぎ（非常に長いセッションで、委任中のものが無い段の区切りに、オーナーへ提案し承認後に行う）: state.md を直し、PR の watch を外し、`t3_thread_launch` で T3 プロジェクトの根（worktree なし）に「state.md を読んで続ける」で立て、リンクを報告して止める。新スレッドは `<orchestration-state>` が文脈にあることを確かめ（無ければ報告して止まる）、PR を watch し直す。
