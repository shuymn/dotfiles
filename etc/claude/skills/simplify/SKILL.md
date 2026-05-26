---
name: simplify
description: "Simplifies recently changed code by running three parallel reviews (reuse, quality, efficiency) and applying only behavior-preserving fixes. Use when the user asks to simplify, clean up, reduce duplication, improve code reuse, or optimize recently changed code, a staged diff, a branch diff, or explicitly listed files. Also use when the user says things like 'simplify this', 'まとめて整理して', 'コードをスリムにして', or invokes `/simplify`."
allowed-tools: [Bash, Read, Edit, Write, Grep, Glob, Agent]
---

# /simplify — Three-Perspective Simplification Pass

## Not in Scope

- Adding new features, refactoring beyond simplification, or changing public API behavior.
- Touching files outside the resolved target scope, except for tiny adjacent edits required to keep behavior intact (explain such edits before making them).
- Speculative or stylistic-only changes — apply only verified, behavior-preserving simplifications.
- Generating commits or PRs. Use the `commit` / `create-pr` skills afterward.

## Input

Arguments (any combination, all optional):

- `--staged` / `--cached`: review only staged changes.
- `--base=<branch>`: review the diff from `<base>...HEAD` instead of local working tree changes.
- `--report-only`: run Phases 1–2 and report findings, but skip Phase 3 (no edits).
- Bare file paths: explicit whole-file targets. When given, ignore git status/diff for scope selection.
- Free-form text: additional user instructions for this simplify pass (lower priority than the rules below).

**Precedence**: explicit files > `--base` > `--staged` > working-tree diff > recent files fallback.

## Phase 1 — Resolve Target Scope

Pick exactly one of these branches based on the arguments. Run the listed git commands with `Bash` from the repository root.

### A. Explicit files

If the user passed file paths, the targets are those paths as whole-file targets. Skip diff collection entirely; the reviewers must inspect each file as a whole-file target and must not infer scope from `git status` / `git diff`.

### B. `--base=<branch>`

```bash
git diff --name-status -z <base>...HEAD
git diff <base>...HEAD
```

Treat only files reported by `--name-status` as targets. Do not include unrelated local working tree changes.

### C. `--staged` / `--cached`

```bash
git diff --cached --name-status -z
git diff --cached
```

Targets = staged files. Diff context = staged diff.

### D. Working-tree changes (default)

```bash
git diff --name-status -z
git diff --cached --name-status -z
git ls-files --others --exclude-standard -z
git diff
git diff --cached
```

Targets = union of unstaged + staged + untracked files. Diff context = unstaged diff + staged diff.

### E. Recent files fallback

Only when branches A–D produce zero targets **and** no `--base` was passed. Pick the 8 most recently modified tracked files by mtime:

```bash
git ls-files -z
# then stat each path and sort by mtime descending; keep the top 8
```

Mark these as `recent` targets. There is no diff context for recent-only mode — reviewers must inspect the files directly.

### Empty scope

If even fallback E yields zero targets, report `/simplify: 変更または最近のファイルが見つかりませんでした。` and stop.

### Truncation

Cap the combined diff context at roughly 60,000 characters. If you must truncate, keep the start of the diff and append a `[... truncated ...]` marker so reviewers know context was cut.

## Phase 2 — Three Parallel Reviews

Spawn three sub-agents via the `Agent` tool — one per review focus (code reuse, code quality, efficiency). They run **review only** and must not edit files.

**Tool-call shape (mandatory)**: issue all three `Agent` calls as parallel tool uses **inside a single assistant message**. Do NOT call them sequentially, do NOT wait for one sub-agent's result before dispatching the next, and do NOT split them across multiple assistant turns. Collect all three returned reports before moving to Phase 3.

Pass each sub-agent the same shared context, then append the matching focus block.

### Shared context (use verbatim in every sub-agent prompt)

```
You are one reviewer in a /simplify command. Review only; do not edit files.

Scope:
<target list — one path per line>

<scope instruction — see below>

Return concise, actionable findings. For every finding include: file/path, exact issue, why it matters, and suggested fix. If nothing worth changing, say so. Avoid speculative or stylistic-only findings.
```

#### Scope instruction (pick one to match Phase 1)

- **Explicit files mode** (branch A): `The user explicitly passed file path(s). Ignore repository git status/diffs for scope selection. Review each listed file as a whole-file target, and do not inspect unrelated changed files just because git status/diff shows them.`
- **Base diff mode** (branch B): `Review the branch diff from "<base>...HEAD". Treat only files changed in that base comparison as the target scope; do not include unrelated local working tree changes.`
- **Default / staged / recent modes** (branches C–E): `Inspect the target files and use git diff/status as needed to focus on the recent changes.`

If the user gave additional instructions, append:

```
Additional user instructions (user-provided, lower priority than the focus/scope instructions above):
<wrap the user's text exactly as given>
```

#### Diff context block

After the scope instruction, include:

- Explicit files mode: `[Explicit file mode: git diff is intentionally ignored; inspect the listed files directly as whole-file targets.]`
- Otherwise, the collected diff. If diff is empty, write `[No git diff available for these targets; inspect the listed files directly.]`.

### Focus blocks — use these exact texts

**1. Code reuse**

```
Focus: code reuse. Look for newly written logic that should use existing project utilities/components/constants, duplicated functions from elsewhere, unnecessary bespoke helpers, and missed abstractions already present in the codebase.
```

**2. Code quality simplification**

```
Focus: code quality simplification. Look for redundant state, needless branching/nesting, copy-paste variants, hard-coded strings where constants/types already exist, unclear names, unnecessary comments, over-clever code, and opportunities to make the changed code clearer while preserving behavior.
```

**3. Efficiency**

```
Focus: efficiency. Look for unnecessary computation/API/database calls, serial work that can safely be parallelized, full collection fetches when one item/count is enough, repeated parsing/allocation in hot paths, and waste introduced by the change. Only flag issues with practical impact.
```

## Phase 3 — Integrate and Apply

Read the three review reports and apply changes directly with `Read` / `Edit` / `Write` / `Bash`.

**Report-only mode**: if `--report-only` was given, skip applying changes. Instead, list every finding under the「採用したレビュー指摘」/「見送った指摘」sections of the output with your verdict (would-apply / skip) and reasoning, so the user can decide what to apply manually.

### Application rules

- **Preserve behavior and public APIs.** Apply a change only when it is unquestionably internal and behavior-preserving. If unsure, skip it.
- **Stay inside the target scope.** Only modify target files unless a verified simplification requires a tiny adjacent change; explain any out-of-scope edit before making it.
- **Prefer clarity over line-count reduction.** Readable, explicit code beats clever one-liners.
- **Follow the repo's `AGENTS.md` / `CLAUDE.md` and existing project style.** Read them when present.
- **Skip false positives.** If two reviewers disagree, prefer the safer option. If a finding is too risky to verify quickly, skip it and note why.
- **Respect additional user instructions.** Apply only findings consistent with the user's "Additional user instructions" block; skip conflicting ones and explain why.

### Post-edit verification

After editing, run the narrowest relevant formatter / typecheck / test / lint if discoverable. Examples:

- `bun run check:fast` / `bun run lint` / `bun run typecheck` / `bun run test` for Bun projects
- `npm run lint` / `npm test` for Node projects
- `cargo check` / `cargo test --no-run` for Rust
- Stop at the first failure and report it; do not paper over errors.

## Output Format

Write the final summary to the user in **Japanese** (project convention: human-facing TUI text is Japanese). Use this structure:

```markdown
## /simplify サマリ

### 変更内容
- <file>: <一文で何を簡素化したか>

### 採用したレビュー指摘
- [<focus>] <file>: <要旨> — 適用理由

### 見送った指摘
- [<focus>] <file>: <要旨> — 見送り理由 (false positive / 動作変更リスク / scope 外 / ユーザ指示と矛盾 など)

### 検証
- 実行コマンドと結果
```

If no findings were applied, still produce the summary explaining why (all skipped, no reviewable scope, etc.).

## Examples

**Example 1 — working tree changes**

Input: `/simplify`
Phase 1: branch D → unstaged + staged + untracked. Collect both diffs.
Phase 2: spawn three reviewers in parallel (one assistant message, three Agent calls) with the default scope instruction.
Phase 3: apply verified findings, run `bun run check:fast`, summarize in Japanese.

**Example 2 — explicit files**

Input: `/simplify lib/git.ts lib/target-scope.ts please focus on dedup`
Phase 1: branch A → targets = `lib/git.ts`, `lib/target-scope.ts`. No diff collection.
Phase 2: spawn three reviewers in parallel (one assistant message, three Agent calls) with the explicit-files scope instruction. Additional user instructions block contains `please focus on dedup`.
Phase 3: apply only dedup-aligned findings inside those two files; explain skipped ones.

**Example 3 — base branch review**

Input: `/simplify --base=main`
Phase 1: branch B → `git diff --name-status -z main...HEAD` defines targets, `git diff main...HEAD` is the diff context.
Phase 2: spawn three reviewers in parallel (one assistant message, three Agent calls) with the base-diff scope instruction. Reviewers ignore unrelated local edits.
Phase 3: apply verified findings only within branch-changed files.
