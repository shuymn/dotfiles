# Regression-unit probe: pre-registration

Committed before any paid run. The probe is advisory, not a gate (docs/kaizen.md section 5): it runs a top-level
session on a synthetic history, and arm B only approximates start-time delivery.

## Question

Does a worker that gets the regression-test unit from the PostToolUse hook, right after its first test-file write,
watch the new test fail and then pass more often than a worker that got the same sentence at the start?

## Arms

Both arms are plugins built by `build`, with the same case, history, packet, fixture and tool grants.

- **A (hook)**: `hooks/hooks.json` sends PostToolUse `Edit|Write|MultiEdit` to `shim.py`, which adds
  `agent_type: "opus-worker"` and `agent_id: "probe-" + session_id` and runs this checkout's
  `home/dot_claude/hooks/executable_orchestration-context.py` with an explicit interpreter. Matching, the
  once-per-agent marker and the text are the real hook's; only the role is simulated.
- **B (start)**: no hook. The unit's `text` from `home/dot_claude/attention/units.json` is a system-reminder at the
  head of the history, before the kickoff, where SessionStart or SubagentStart text would land.

## Case

The pilot-3 worker case: worker-7 in an orchestration gets packet #12 ("fix `page_count` rounding down and add a
regression test"; the brief wrongly says tests for `page_slice` exist) early in a level-2 history of ten unrelated
packets from public merge commits of this repository at a pinned revision, then the go-ahead. The kickoff
carries the body of the checkout's `home/dot_claude/agents/opus-worker.md` as it is when `build` runs.

- `scaffold.sh` writes `paginate.py`, `test_clock.py`, `README.md` and `VERSION` into the working directory before
  the session starts, the same bytes in both arms, so no setup write can match `test_*.py` and use up the unit.
- Tools: Read, Glob, Grep, Bash, Write, Edit; grants Bash, Write, Edit. Max 40 turns, 600 s.
- Level 0 (clean prompt, no history) exists only for the calibration of arm A.

## Grader (scored)

`t-seen-fail2`, computed offline by `score` from the run's stream-json trace. Each Bash `tool_use` is joined to its
`tool_result` by id. A run passes when one test run's output shows the new pagination test failing on an assertion
(a unittest `FAIL:` block with `AssertionError`, or a pytest `FAILED ... - assert` line, in a module other than
`test_clock`, whose test name, traceback source lines or assertion message name `page_count`, pages or
pagination) and another test run, before or after it, shows that same test passing (its
verbose `... ok` line, pytest `PASSED`, or `OK` from a command naming its module). A command that itself contains
failure or pass text (printf, echo) is not a test run. `ERROR:` blocks (import or syntax errors) never count.

## Indicators (not scored)

- `ind-delivered` (arm A): a hook-origin record holding the unit text, tied by tool use id to a successful write
  that the hook's own matcher counts as eligible: a `hook_additional_context` attachment in the session transcript
  kept from the run's temp directory, or a `hook_response` system record in the trace. The model repeating the
  sentence does not count. Also recorded: the first eligible write and whether the delivery was tied to it.
- The P3 regex `t-seen-fail` as the eval reports it, turns, final message length, cost.
- `shim.log` per run: each hook call and whether the hook printed anything.

## Runs and win rule

- Calibration: one level-0 run of arm A. `ind-delivered` 0 stops the probe; the fallback is decided then, never a
  simulated arm A.
- Probe: 6 level-2 runs per arm, in shuffled order, one eval call per run.
- A side wins with at least 5/6 and more than the other arm. A wins or nobody wins: keep PostToolUse delivery.
  B wins: stop and put the choice to the owner.
- An errored run with no turns is rerun once, no more. An arm with fewer than 6 complete runs makes the comparison
  inconclusive. Runs that hit max turns or the timeout keep their turns and are scored as they are.

## Cost

One envelope of 5.00 USD for the eval runs under the output directory: calibration (about 0.20 USD) and 12 probe
runs (pilot 3 measured 0.28 to 0.39 USD per level-2 worker run, about 3.80 USD in all). The real-worker smoke check
is a separate `claude -p` run with its own `--max-budget-usd 1.00`, recorded apart from the probe. Each eval call
gets `--max-cost-usd` equal to what is left, and no run starts with less than 0.30 USD left.

## Isolation

Each run has a fresh `HOME` and `TMPDIR` (also passed to the hook as `EVAL_KAIZEN_PROBE_TMPDIR`), so live hooks and
settings never load and the unit markers of one run never reach another, although all runs resume the same session
id. The real `claude` executable is resolved before `HOME` changes. Every call passes `--no-publish`. Only
directories a run created are deleted.

## Recorded with the result

CLI version and model (from the eval result and the trace), the pinned filler revision (`build.json`), per-arm
`t-seen-fail2`, `ind-delivered`, cost and the rule outcome. Raw traces stay local; a PR gets counts and cost only.

## Commands

```sh
scripts/kaizen/probe/build --out "$OUT"
scripts/kaizen/probe/run --out "$OUT" --case worker-L0 --arms A --runs 1
scripts/kaizen/probe/score --out "$OUT" --case worker-L0 --arms A --runs 1
scripts/kaizen/probe/run --out "$OUT"
scripts/kaizen/probe/score --out "$OUT"
```
