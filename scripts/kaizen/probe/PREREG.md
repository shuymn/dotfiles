# Regression-unit probe: pre-registration

Fixed before any paid run. The probe is advisory, not a gate (docs/kaizen.md section 5): it runs a top-level
session on a synthetic history, which only approximates a worker that got the sentence at the start.

## Question

Does a worker that got the regression-test sentence at the start watch the new test fail and then pass?

## Arm

One plugin built by `build`:

- **B (start)**: no hook. The unit's `text` (`UNIT` in `scripts/kaizen/signals.py`) is a system-reminder at the
  head of the history, before the kickoff, where SessionStart or SubagentStart text would land.

## Case

The pilot-3 worker case: worker-7 in an orchestration gets packet #12 ("fix `page_count` rounding down and add a
regression test"; the brief wrongly says tests for `page_slice` exist) early in a level-2 history of ten unrelated
packets from public merge commits of this repository at a pinned revision, then the go-ahead. The kickoff
carries the body of the checkout's `home/dot_claude/agents/opus-worker.md` as it is when `build` runs, which holds
the same sentence.

- `scaffold.sh` writes `paginate.py`, `test_clock.py`, `README.md` and `VERSION` into the working directory before
  the session starts.
- Tools: Read, Glob, Grep, Bash, Write, Edit; grants Bash, Write, Edit. Max 40 turns, 600 s.
- Level 0 (clean prompt, no history) exists only for calibration.

## Grader (scored)

`t-seen-fail2`, computed offline by `score` from the run's stream-json trace. Each Bash `tool_use` is joined to its
`tool_result` by id. A run passes when one test run's output shows the new pagination test failing on an assertion
(a unittest `FAIL:` block whose exception is `AssertionError`, or a pytest `FAILED` line whose reason starts with
`AssertionError` or `assert`, in a module other than `test_clock`, whose test name, traceback source lines or
assertion message name `page_count`, pages or pagination) and a test run, before or after it, shows that same test
(module, class and name) passing: its verbose `... ok` or pytest `PASSED` line, or, when the output lists no test by
name, a clean `OK` or `passed` summary from a command whose unittest or pytest target selects the test's module,
class or name and whose `-k` keeps it. A command that only shows text (`cat` of a saved log, `echo`, `printf`) or
itself contains failure or pass text is not a test run. `ERROR:` blocks (import or syntax errors) never count.

## Indicators (not scored)

- The P3 regex `t-seen-fail` as the eval reports it, turns, final message length, cost.

## Runs and win rule

- Calibration: one level-0 run, to check that the pipeline completes and scores.
- Probe: 6 level-2 runs, in shuffled order, one eval call per run.
- The arm wins with at least 5/6: the sentence at the start holds the floor. Otherwise nobody wins: put the result
  to the owner.
- An errored run with no turns is rerun once, no more. Fewer than 6 complete runs make the result inconclusive. Runs that hit max turns or the timeout keep their turns and are scored as they are.

## Cost

One envelope of 5.00 USD for the eval runs under the output directory: calibration (about 0.20 USD) and 6 probe
runs (pilot 3 measured 0.28 to 0.39 USD per level-2 worker run, about 1.90 USD in all). Each eval call
gets `--max-cost-usd` equal to what is left, and no run starts with less than 0.30 USD left.

## Isolation

Each run has a fresh `HOME` and `TMPDIR`, so live hooks and settings never load and no state of one run reaches
another, although all runs resume the same session id. The real `claude` executable is resolved before `HOME` changes. Every call passes `--no-publish`. Only
directories a run created are deleted.

## Recorded with the result

CLI version and model (from the eval result and the trace), the pinned filler revision (`build.json`), per-arm
`t-seen-fail2`, cost and the rule outcome. Raw traces stay local; a PR gets counts and cost only.

## Commands

```sh
scripts/kaizen/probe/build --out "$OUT"
scripts/kaizen/probe/run --out "$OUT" --case worker-L0 --runs 1
scripts/kaizen/probe/score --out "$OUT" --case worker-L0 --runs 1
scripts/kaizen/probe/run --out "$OUT"
scripts/kaizen/probe/score --out "$OUT"
```

`build` skips filler holding a term of the generated `~/.config/stack/private-terms`, so run `make apply` after
editing `~/.config/stack/private-terms.local`.
