# Workflow

<!-- 更新原則は append ではなく rewrite とする。新しい論点が出たら追記せず、全体を削って書き直し、今の最小運用仕様だけを残す。 -->

## Flow

永続文書は `Roadmap`、`Design Doc`、`ADR`, `TODO.md` に絞る。

流れは次の通り。

`Roadmap -> Design Doc & ADR -> TODO.md -> 実装`

---

## Decomposition Principle

分解は縦方向に行う。

この文書でいう `縦` とは、層、部品、工程ごとの分解ではなく、「1つ終わると外から何が前進したかが観測できる単位」を指す。以後、この単位を `縦テーマ` と呼ぶ。判断基準は内部構造ではなく、ユーザー、呼び出し元、運用者、外部システムのいずれかから見て、何が新しくできるようになったか、何が安全に保証されるようになったかである。

この文書でいう `横` とは、parser、IR、renderer のような層、API と DB のような部品、実装、テスト、リファクタのような工程都合で分けることを指す。横分解は実装作業の棚卸しには使えても、Roadmap と TODO の主要単位にはしない。

`Roadmap`、`Design Doc`、`TODO.md` はすべてこの原則に従う。特に `TODO.md` の `Theme` は、内部の作業束ではなく、縦テーマでなければならない。

---

## Verification Taxonomy

verification taxonomy は `static | unit | integration | system` に揃える。`system` は e2e を含む。Theme は required verification coverage に含めた全 level を満たす必要がある。

coverage の基本方針は `integration-first` とする。

- 全 Theme で `static` は必須とする。
- `integration` は default で必須とする。外から観測できる前進、境界接続、契約、状態遷移を Theme 完了条件に含むなら `integration` を外さない。
- `unit` は `integration` の代替ではなく追加 level とする。局所責務や局所 contract の破綻を、`integration` より安く早く強く検出したいときに追加する。
- `system` は主要シナリオ、ユーザー価値、stop-ship 条件を Theme 完了条件に含むときだけ追加する。

各 level の定義は次の通り。

- `static`
  静的解析、型、lint、禁止依存などの即時 gate。evidence は `executor/check identifier + case/suite/scenario identifier + pass/fail + replay handle`。
- `unit`
  局所責務、モジュール、関数、unit-level contract。evidence は `executor/check identifier + case/suite/scenario identifier + pass/fail + replay handle`。
- `integration`
  境界接続、API/CLI 契約、状態遷移、integration-level reject。evidence は `executor/check identifier + case/suite/scenario identifier + pass/fail + replay handle`。
- `system`
  主要シナリオ、ユーザー価値、stop-ship 条件、e2e-level reject。evidence は `executor/check identifier + case/suite/scenario identifier + pass/fail + replay handle`。

---

## Artifact Definitions

### Roadmap

長期テーマ、到達像、進行順のラフな方向を保持する。まだ `Design Doc` 化するには早いが、単なるアイデアメモではなく「どこへ進むか」を示す。

`Roadmap` でも横方向の分解は避ける。ここでの `Theme` は、縦テーマとして書く。

- `Theme`
  どの長期テーマを前進させるかを書く。
- `Outcome`
  そのテーマが進むと何ができるようになるかを書く。
- `Why it matters`
  なぜそれが重要か、何を前進させるかを書く。
- `Vertical Tension`
  その縦テーマから `Design Doc` で固定すべき判断を導く時に、まだ固定されていない設計上の張力だけを書く。部品分割の論点一覧ではなく、「この `Theme` を縦テーマとして成立させるには何を解かなければならないか」に寄せる。

`Roadmap` には固定技術選定、実装順の詳細、細粒度タスク、`Reject if` を書かない。

### Design Doc

`TODO.md` に落とす前に固定すべき判断を持つ source of truth。

`Roadmap` の `Vertical Tension` に含まれる open question を解消して固定した判断の canonical source は ADR とする。`Design Doc` は構造、制約、verification を持ち、固定判断は `ADR References` で参照する。判断が衝突した場合は ADR を優先する。

- `Goal`
  この設計で成立させたいことを書く。
- `Scope / Non-Scope`
  今回扱う範囲と、意図的に扱わない範囲を書く。
- `Architecture / Responsibility`
  どこに責務を置くか、どの境界で分けるかを書く。
- `ADR References`
  open question を解消して固定した技術選定や採否判断として参照すべき ADR を列挙する。
- `Constraints`
  fail-closed、互換性、変更境界など、破ってはいけない制約を書く。
- `Verification Strategy`
  Theme の性質ごとに required verification coverage をどう決めるか、何で妥当性を確かめるかを書く。

`Design Doc` に残すのは、少なくとも次の入力になるものだけとする。

- `TODO Input`
  これがないと縦テーマを切れないもの。
- `Gate Input`
  これがないと `Reject if` や `Verification` を決められないもの。
- `Execution Input`
  これがないと安全に実行単位へ切れないもの。

`Reference Only` は原則残さない。

### ADR

`Roadmap` の `Vertical Tension` に含まれる open question を解消して固定した判断を記録する。

ADR は技術選定や採否判断の canonical source であり、`Design Doc` から参照される。少なくとも次を持つ。

- `Status`
  提案中、採用、廃止など、判断の状態を書く。
- `Context`
  何を決める必要があり、どの open question を解消するのかを書く。
- `Decision`
  何を採用したかを書く。
- `Rejected Alternatives`
  今回採らない案を書く。
- `Consequences`
  その判断により何が固定され、何が影響を受けるかを書く。

判断が衝突した場合は ADR を優先する。

### TODO.md

未完了の縦テーマを管理する。TODO は実行命令書ではなく、テーマ管理のハブとする。

基本原則は、TODO を横分解ではなく縦テーマで書くこと。ここでの `Theme` は縦テーマを指す。

`Why not split further?` は補足ではなく、分割停止条件である。これに具体的に答えられない Theme は、まだ粒度が悪いとみなす。

- `Theme`
  何を前進させる縦テーマかを書く。
- `Outcome`
  終わると外から何ができるようになるかを書く。
- `Why now`
  なぜ今この Theme を進めるのかを書く。
- `Verification`
  Theme に必要な required verification coverage を書く。`static | unit | integration | system` を使い、`system` には e2e を含む。
- `Reject if`
  何なら今は採用不可かを書く。各項目は `[static]`、`[unit]`、`[integration]`、`[system]` の owner tag を持つ。
- `Why not split further?`
  なぜこの粒度で止めるのかを書く。

最小形は次。

```md
- [ ] Theme: ...
  - Outcome: ...
  - Why now: ...
  - Verification: static + integration
  - Reject if:
    - [static] ...
    - [integration] ...
    - [integration] ...
  - Why not split further?: ...
```

---

## Author Guide

### Roadmap Author

- `Goal`
  発散したアイデアを、`Design Doc` の起点になる縦テーマへ圧縮する。
- `Context`
  実行時の active context を増やさず、後で `TODO.md` が横方向の分解チェックリストにならないようにする。
- `Done when`
  各項目が `Theme`、`Outcome`、`Why it matters`、`Vertical Tension` を持ち、縦テーマとして読める。`Vertical Tension` は `Design Doc` の `Goal`、`Architecture / Responsibility`、`Constraints`、`Verification Strategy` の少なくとも1つに展開できる。
- `Constraints`
  `Vertical Tension` は layer ごとの TODO 候補を書き並べる欄ではない。`parser`、`IR`、`renderer` のような横分解を誘発する書き方は避ける。新しい論点は追記で増築せず、必要なら全体を rewrite する。

### Design Doc Author

- `Goal`
  `Roadmap` の縦テーマについて、open question を解消し、`TODO.md` に落とす前に必要な固定判断を明確にする。
- `Context`
  `Roadmap` よりは具体化するが、実装命令書にはしない。`TODO Input`、`Gate Input`、`Execution Input` を成立させるための source of truth に留める。
- `Done when`
  `Goal`、`Scope / Non-Scope`、`Architecture / Responsibility`、`ADR References`、`Constraints`、`Verification Strategy` が揃い、`TODO.md` に落とすために必要な固定判断が埋まっている。少なくとも、主要責務の置き場所、必要な ADR 判断、verification taxonomy、Theme 単位の required verification coverage が未確定ではない。
- `Constraints`
  `Reference Only` を原則残さない。open question を解消して固定した技術選定や採否判断は ADR に寄せ、`Design Doc` にはその判断の参照だけを残す。詳細実装順、細粒度タスク、`Reject if` は書かない。新しい論点は追記で増築せず、必要なら全体を `rewrite` する。

### TODO Author

`Design Doc` から直接実装タスクを作らず、まず外から観測できる前進として縦テーマ候補を出す。その後で `Architecture / Responsibility` と `Verification Strategy` を使って、その候補が成立するかを確かめる。

TODO の単位は縦テーマとする。層、部品、内部実装都合だけでは切らない。

- `Goal`
  `Design Doc` の固定判断を、実装順ではなく複数の縦テーマへ分解して `TODO.md` の backlog にする。
- `Context`
  TODO は実行命令書ではなく、テーマ管理のハブである。横分解チェックリストではなく、縦テーマの backlog として保つ。
- `Done when`
  各 Theme について `Outcome`、`Why now`、`Verification`、`Reject if`、`Why not split further?` が具体化されている。`Goal` とつながり、`Outcome` から外からの前進が観測でき、`Why now` で着手理由を説明でき、required verification coverage と `Reject if` owner tag を決められ、未確定の ADR 判断に依存しない。さらに、required verification coverage の各 level について「何を示せば通過と言えるか」が `Reject if` から追える。
- `Constraints`
  実装量の最小ではなく、設計の妥当性を最も早く検証できる Theme を先に進める。`Why not split further?` が書けない Theme はまだ分割が悪く、TODO に置かない。required verification coverage は Verification Taxonomy の coverage 方針に従う。

Evidence readiness:

- required verification coverage の各 level に、少なくとも1つの `Reject if` owner tag を対応づける
- `Reject if` は抽象語ではなく、fail 条件として観測可能に書く
- `Verification` は level 名の列挙だけで終わらせず、その level で何を証明する必要があるかを `Outcome` と `Reject if` の組で読めるようにする
- reviewer や gatekeeper が「どの evidence があれば十分か」を逆算できない Theme は、まだ TODO に置かない

`Reject if` は最低でも次の型に寄せる。

- `[integration]` 機能未達
- `[static|integration|system]` 禁止違反
- `[integration|system]` 回帰
- `[static|integration]` 境界逸脱
- `[static|unit|integration|system]` evidence 不足

---

## Reviewer Guide

`review` と `gate` は分ける。`review` は `Divergent Review` とし、甘く通さず厳しく見るが、採用可否は裁定しない。

### What To Review

- `Roadmap`
  縦テーマとして読めるか。`Vertical Tension` が横分解の論点一覧になっていないか。
- `Design Doc`
  主要責務の置き場所、必要な ADR 判断、verification taxonomy、Theme 単位の required verification coverage など、`TODO.md` に進むための固定判断だけが残っているか。`Reference Only` や現状説明が紛れ込んでいないか。
- `TODO.md`
  `Theme` が縦テーマとして成立しているか。`Outcome`、`Verification`、`Reject if`、`Why not split further?` が弱くないか。特に `Why not split further?` が分割停止条件として具体的に機能しているか。
- `実装`
  コード変更そのものではなく、特定の `Theme` を満たす実装変更とその evidence bundle を review する。`Outcome`、`Verification`、`Reject if`、対応する `Design Doc` の `Architecture / Responsibility`、`Constraints`、ADR 判断と整合しているか、境界逸脱、回帰リスク、evidence の弱さがないかを見る。

### Reviewer Output

- 甘く通さず、問題になりうる点を厳しく指摘する
- owner tag と verification level の候補があれば添える
- `実装` については、関連する `Theme`、疑わしい `owner tag` / verification level、未充足の `Reject if` 候補、evidence gap を添える
- `reject-now`、`need-evidence` の裁定はしない

---

## Review and Gate Flow

1. `Divergent Review` が指摘候補を出す（全 artifact 共通）
2. `Convergent Gate` が裁く
   - `Roadmap` / `Design Doc`: 各 Quality Gate の `reject-now` 条件で裁く
   - `TODO.md`: 各 Quality Gate の `reject-now` / `need-evidence` 条件で、文書構造と evidence readiness を裁く
   - `実装`: `Theme identifier`、対応する `Verification` / `Reject if`、evidence mapping、verification evidence で裁く
3. `reject-now` と `need-evidence` だけが採用可否に影響する
4. `実装` の `Convergent Gate` は、対象 `Theme` の required verification coverage を次の順で実行する
   1. `static`（常に必須）
   2. `unit` / `integration` / `system`（Theme の required verification coverage に含まれるもの）

---

## Gatekeeper Guide

`gate` は `Convergent Gate` とし、`Reject if` と `Verification evidence` で裁定する。

### Roadmap Quality Gate

- `reject-now` if `Theme`、`Outcome`、`Why it matters`、`Vertical Tension` のいずれかが欠けている
- `reject-now` if 横分解の論点一覧、実装順、細粒度タスク、固定技術選定が主になっている
- `reject-now` if `Vertical Tension` から、固定すべき責務・制約・verification の論点を引けない

### Design Doc Quality Gate

- `reject-now` if 主要責務の置き場所が未確定
- `reject-now` if 必要な ADR 判断が未確定
- `reject-now` if verification taxonomy が未確定
- `reject-now` if Theme 単位の required verification coverage が未確定
- `reject-now` if `Reference Only` や現状説明が主になっている
- `reject-now` if 対応する `Roadmap` 項目の `Theme`、`Outcome`、`Why it matters` をこの `Design Doc` で満たす構造になっていない
- `reject-now` if 対応する `Roadmap` 項目の `Vertical Tension` に対して、固定すべき責務・制約・verification の論点が受け止められていない

### TODO.md Quality Gate

- `reject-now` if `Outcome`、`Verification`、`Reject if`、`Why not split further?` のいずれかが欠けている
- `reject-now` if `Why not split further?` により、この `Theme` をこれ以上割らない理由が具体的に示されていない
- `reject-now` if required verification coverage の各 level に対応する `Reject if` owner tag を置けない
- `reject-now` if 対応する `Design Doc` の `Goal`、`Architecture / Responsibility`、`Constraints`、`Verification Strategy` をこの `TODO.md` の Theme 群で満たせない
- `reject-now` if いずれかの Theme が未確定の ADR 判断や未固定の責務配置に依存している
- `need-evidence` if required verification coverage の各 level について、何を示せば通過かを `Verification` と `Reject if` から引けない

### Implementation Quality Gate

- `reject-now` if 実装が対象 `Theme` の `Outcome` を満たさない
- `reject-now` if 実装が対応する `Design Doc` の `Architecture / Responsibility`、`Constraints`、ADR 判断に反する
- `reject-now` if required verification coverage に対応する実装または検証経路が存在しない
- `reject-now` if 対象 `Theme` の `Reject if` のいずれかが実際に成立している
- `need-evidence` if evidence が対象 `Theme` の required verification coverage、`Reject if` owner tag、pass/fail 判定に紐付かない
- `need-evidence` if evidence が未実行、replay 不可能、または `executor/check identifier + case/suite/scenario identifier + pass/fail + replay handle` を満たさない
- `need-evidence` if どの evidence がどの `Theme` のどの `Verification` / `Reject if` を満たすかを逆算できない

### Gate Output

- `pass`
  現時点で gate を止める理由がなく、対象 artifact または実装を次へ進めてよい。
- `reject-now`
  今の状態では通せず、artifact 自体または実装の修正が必要である。
- `need-evidence`
  通過判断に必要な evidence が不足しており、追加の根拠が必要である。

`need-evidence` は required verification coverage に対する evidence contract のいずれかが欠けているときに使う。未実行またはラベルだけの identifier は evidence とみなさない。`need-evidence` の適用範囲は `TODO.md Quality Gate` と `Implementation Quality Gate` に限る。`Roadmap Quality Gate` と `Design Doc Quality Gate` は構造・充足性の検査であり、verification evidence を伴わないため `reject-now` のみで裁定する。

対象 `Theme` の required verification coverage の全 gate に `reject-now` と `need-evidence` がなければ `pass` として proceed してよい。

owner tag は `static | unit | integration | system` のみとする。
