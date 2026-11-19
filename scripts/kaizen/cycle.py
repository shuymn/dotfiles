#!/usr/bin/env python3
"""The kaizen daily cycle (docs/kaizen.md §6): one stateless run over the last 7 days. No model is called.

  cycle.py [run]            apply merged changes first (apply.py; --no-apply skips it), then observe, watch and
                            readiness from scratch, then write record.json, digest.md and
                            status.json into a new directory K/runs/<id> and publish the whole run in one step: the
                            symlink K/current is replaced by rename to point at it (K = $KAIZEN_HOME, else
                            ~/.claude/kaizen; the run date is in Asia/Tokyo). Readers go through K/current. A run that
                            fails, is killed or passes --deadline before it starts publishing leaves K/current as it was,
                            which the statusline shows stale by its time. After a publish, run directories other than
                            the published one and the one it replaced are deleted.
  cycle.py baseline <id>    write the pre-apply aggregate of watch.json's change <id> to K/watch/<id>.json, once (an
                            existing file is left alone). Transcripts are deleted after 30 days, so the daily run uses
                            this file for the pre window when it is there.
  cycle.py adopt <sha>      record <sha> as the applied commit, after printing what it skips (apply.adopt)
  cycle.py resolve [--yes]  print the unresolved apply journal; --yes clears it and nothing else (apply.resolve)
Watch (watch.json): per change, the regression signal of signals.py over pre [apply - 30 d, apply] and post
[apply, min(now, apply + days)]; a worker active across apply is counted in both windows.
The last stdout line is a JSON summary; progress goes to stderr.
"""
import sys

sys.dont_write_bytecode = True  # the siblings must not leave .pyc files in the checkout

import argparse
import fcntl
import importlib.util
import json
import os
import re
import shutil
import signal
import stat
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sibling(name):
    spec = importlib.util.spec_from_file_location(f"kaizen_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


apply = sibling("apply")
observe = sibling("observe")
ready = sibling("ready")
signals = sibling("signals")

WINDOW_DAYS = 7
PRE_DAYS = 30
CHANGE_ID = re.compile(r"[A-Za-z0-9#._-]+")
REGRESSION_KEYS = ("window", "workers", "opportunities", "counted", "ambiguous", "not_counted", "rate", "harm")
EXAMPLES = 3
DEADLINE = 1200  # seconds a whole run may take; a normal one takes under 2 minutes
RUN_NAME = re.compile(r"\d{8}T\d{6}-[a-z0-9_]{8}")  # the names publish_run gives (mkdtemp's random suffix)


def log(msg):
    print(f"kaizen: {msg}", file=sys.stderr, flush=True)


def publish(path, text):
    """Write text beside path and rename it into place; the temp file is removed if anything stops the write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def publish_run(k, record, files):
    """Write files into a new K/runs/<id>, point K/current at it by one rename, then delete older run directories but
    this one and the previous one. Publishers take turns on K/.publish.lock (a run started by hand may overlap the
    launchd run). A stop or the deadline while waiting for the lock ends the run unpublished; once the lock is held,
    SIGTERM and SIGALRM wait until the publish is done, so a stop never undoes or half-does it. A prune that fails is
    logged, not raised, because the run is already published. Returns the run directory."""
    runs = k / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    with open(k / ".publish.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)  # released when the file closes or the process dies
        held = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGALRM})
        try:
            run_dir = Path(tempfile.mkdtemp(dir=runs, prefix=f"{datetime.now(observe.TZ):%Y%m%dT%H%M%S}-"))
            name, current = run_dir.name, k / "current"
            link = k / f".current.{name}"
            try:
                for file, text in files.items():
                    (run_dir / file).write_text(text, encoding="utf-8")
                previous = os.readlink(current) if current.is_symlink() else None
                os.symlink(f"runs/{name}", link)
                os.replace(link, current)  # the publish: one rename
            except BaseException:
                link.unlink(missing_ok=True)
                shutil.rmtree(run_dir)
                raise
            keep = {name, Path(previous).name if previous else None}
            for entry in runs.iterdir():
                # only directories this script names, checked without following a symlink
                if entry.name not in keep and RUN_NAME.fullmatch(entry.name) and stat.S_ISDIR(entry.lstat().st_mode):
                    try:
                        shutil.rmtree(entry)
                    except OSError as e:
                        log(f"prune: {entry}: {e}")
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, held)
    return run_dir


def regression(projects, since, until):
    days = (until - since).total_seconds() / 86400
    r = signals.regression(str(projects), days=days, now=until)
    return {k: r.get(k) for k in REGRESSION_KEYS}


def watch_entries(path):
    entries = json.loads(Path(path).read_text())
    for e in entries:
        if not CHANGE_ID.fullmatch(str(e.get("change"))):
            raise ValueError(f"invalid change id {e.get('change')!r}")
    return entries


def watch(k, projects, now, watch_file):
    out = []
    for e in watch_entries(watch_file):
        change, apply = e["change"], observe.parse_time(e.get("apply") or "")
        row = {"change": change, "signal": e.get("signal"), "apply": e.get("apply"), "pre": None, "post": None}
        out.append(row)
        if e.get("signal") != "regression" or apply is None:
            row["status"] = "unsupported entry"
            continue
        try:
            saved = k / "watch" / f"{change}.json"
            if saved.exists():
                row["pre"], row["pre_source"] = json.loads(saved.read_text())["pre"], "snapshot"
            else:
                row["pre"] = regression(projects, apply - timedelta(days=PRE_DAYS), apply)
                row["pre_source"] = "live" + (", partial: older transcripts deleted" if now > apply else "")
            close = apply + timedelta(days=int(e.get("days") or 28))
            end = min(now, close)
            row["post"] = regression(projects, apply, end) if end > apply else None
            row["status"] = "closed" if now >= close else "open"
        except Exception as ex:  # noqa: BLE001 — a broken watch is reported, not fatal
            row["status"] = f"unavailable: {type(ex).__name__}: {ex}"
    return out


def baseline(k, projects, watch_file, change, now):
    entry = next((e for e in watch_entries(watch_file) if e["change"] == change), None)
    if entry is None:
        raise SystemExit(f"kaizen: {change} is not in {watch_file}")
    path = k / "watch" / f"{change}.json"
    if path.exists():
        log(f"{path} exists; left as it is")
        return {"baseline": str(path), "written": False}
    apply = observe.parse_time(entry["apply"])
    pre = regression(projects, apply - timedelta(days=PRE_DAYS), apply)
    publish(path, json.dumps({"change": change, "apply": entry["apply"], "saved": observe.iso(now), "pre": pre},
                             indent=2, ensure_ascii=False) + "\n")
    return {"baseline": str(path), "written": True}


def decisions(record):
    found = []
    for rid, r in record["ready"].items():
        if r["status"] == "FAIL" and r["owner"]:
            found.append(f"{rid} FAIL: {text(r['detail'])}")
    for name, s in record["sources"].items():
        if s["status"] == "fail":
            found.append(f"source {name} failed: {s.get('error')}")
    for w in record["watch"]:
        if w.get("status", "").startswith("unavailable"):
            found.append(f"watch {w['change']} {w['status']}")
    found += record["apply"].get("decisions", [])
    return found


def text(v):
    return " ".join(("; ".join(map(str, v)) if isinstance(v, list) else str(v)).split())


def regression_text(r):
    if not r:
        return "未観測"
    if not r.get("opportunities"):
        return f"未観測（worker {r.get('workers')}、機会 0）"
    harm = "; ".join(f"{k} turns {g.get('median_turns')}, 報告 {g.get('median_report_chars')} 字"
                     for k, g in (r.get("harm") or {}).items() if isinstance(g, dict))
    return (f"機会 {r['opportunities']}, 数えた {r.get('counted')}, 曖昧 {r.get('ambiguous')}, 率 {r.get('rate')}"
            + (f"; 害: {harm}" if harm else ""))


def apply_lines(a):
    """The apply section: always the stored cursor and the journal (N5), then this run's merges."""
    c = a.get("cursor")
    lines = [f"- 位置: {c['commit'][:12]}（{c['by']}、{c['at']}）" if c else
             "- 位置: 未設定（判断事項の `cycle.py adopt <sha>` で決める）",
             f"- 今回: {a.get('status')}" + (f"（{a['reason']}）" if a.get("reason") else "")
             + (f"、main {a['head'][:12]}" if a.get("head") else "")
             + (f"、管理パスに触れないコミット {a['passed']} 件を通過" if a.get("passed") else "")]
    for m in a.get("merges", []):
        lines.append(f"- {m.get('pr') or m['commit'][:8]} {m['status']}" + (f": {m['reason']}" if m.get("reason") else ""))
        lines += [f"  - {t}: {k}" for t, k in m.get("targets", {}).items()]
    journal = [e for e in a.get("journal") or [] if e.get("step") != "clean"]
    lines.append(f"- 未解決の journal: {len(journal)} 件")
    lines += [f"  - {e['target']}（{e.get('step')}）: backup {e['backup']}" + (f" — {e['note']}" if e.get("note") else "")
              for e in journal]
    return lines


def digest(record):
    lines = [f"# kaizen {record['date']}", "", f"窓: {record['window']['since']} – {record['window']['until']}"
             f"（{record['secs']} 秒で計算）", "", "## 準備状態"]
    lines += [f"- {rid} {r['status']}{' (owner)' if r['owner'] else ''}: {text(r['detail'])}"
              for rid, r in record["ready"].items()]
    lines += ["", "## 適用", *apply_lines(record["apply"])]
    lines += ["", "## 取りこぼしと無駄"]
    for sig, n in record["counts"].items():
        lines.append(f"- {sig}: {n}")
        lines += [f"  - {it['where']} — {it['excerpt']}" for it in
                  [it for it in record["items"] if it["signal"] == sig][:EXAMPLES]]
    t = record["tally"]
    lines.append(f"- オーナーの発言: owner {t['owner']}, unknown {t['unknown']}, synthetic {t['synthetic']}")
    lines += [f"- source {n}: {s['status']}, files {s['files']}, records {s['records']}, bad_lines {s['bad_lines']}, "
              f"{s['secs']}s" + (f" — {s['error']}" if s.get("error") else "") for n, s in record["sources"].items()]
    lines += ["", "## 監視中の変更"]
    for w in record["watch"]:
        lines.append(f"- {w['change']} {w['signal']}（適用 {w['apply']}）: {w.get('status')}")
        lines.append(f"  - 前（{w.get('pre_source', '—')}）: {regression_text(w['pre'])}")
        lines.append(f"  - 後: {regression_text(w['post'])}")
    if not record["watch"]:
        lines.append("- なし")
    lines += ["", "## 判断事項", *([f"{i}. {d}" for i, d in enumerate(record["decisions"], 1)] or ["- なし"])]
    lines += ["", "## 費用", "- Claude $0、Codex $0（モデルを呼ばない）", "- 元の行: 同じディレクトリの record.json", ""]
    return "\n".join(lines)


def run_apply(home, repo, args, started):
    """The apply stage (K5): in-process, first, within the run's deadline. An error is reported, never raised, so
    observe and publish go on; SIGTERM and the deadline take the run's own exit path."""
    if args.no_apply:
        result = {"status": "off"}
    else:
        log("apply")
        try:
            return apply.run(home, repo, deadline=started + args.deadline)
        except Exception as e:  # noqa: BLE001 — a broken apply is its own decision
            result = {"status": "error", "reason": f"{type(e).__name__}: {e}",
                      "decisions": [f"apply crashed: {type(e).__name__}: {e}"]}
    try:
        result.update(apply.persisted(home))
    except (OSError, ValueError, KeyError) as e:
        result["reason"] = (result.get("reason") or "") + f"; apply state unreadable: {e}"
    return result


def run_cycle(k, home, now, args):
    started = time.monotonic()
    repo = ready.source_repo(args.chezmoi)
    applied = run_apply(home, repo, args, started)
    paths = observe.default_paths(home)
    if args.no_t3:
        paths["t3_db"] = None
    since = now - timedelta(days=WINDOW_DAYS)
    log(f"observe {observe.iso(since)} – {observe.iso(now)}")
    obs = observe.observe(paths, since, now, gh=None if args.no_gh else args.gh)
    log("watch")
    watched = watch(k, paths["projects"], now, args.watch_file)
    log("ready")
    today = now.astimezone(observe.TZ).date().isoformat()
    checks = {
        "R1": lambda: ready.check_r1(home, repo, args.chezmoi),
        "R2": lambda: ready.check_r2(args.launchctl),
        "R3": lambda: ready.check_r3(home),
        "R4": lambda: ready.check_r4(obs["sources"], args.gh),
        "R5": lambda: ready.check_r5(k, now, repo and observe.origin_repo(str(repo)), args.gh),
    }
    results = {}
    for rid, check in checks.items():
        try:
            results[rid] = check()
        except Exception as e:  # noqa: BLE001 — one broken check is its own FAIL
            results[rid] = ready.result(False, f"check crashed: {type(e).__name__}: {e}")
    record = {"date": today, **{key: obs[key] for key in ("window", "sources", "counts", "tally", "codex_sessions")},
              "ready": results, "apply": applied, "watch": watched, "items": obs["items"], "cost": {"claude_usd": 0, "codex_usd": 0}}
    record["decisions"] = decisions(record)
    record["secs"] = round(time.monotonic() - started, 1)
    record["finished"] = observe.iso(datetime.now(timezone.utc))
    status = {"date": today, "fail": sum(r["status"] == "FAIL" for r in results.values()),
              "decisions": len(record["decisions"]), "last_completed_epoch": int(time.time())}
    run_dir = publish_run(k, record, {"record.json": json.dumps(record, indent=1, ensure_ascii=False) + "\n",
                                      "digest.md": digest(record), "status.json": json.dumps(status) + "\n"})
    return {**status, "run": str(run_dir), "secs": record["secs"], "counts": record["counts"],
            "sources": {n: s["status"] for n, s in obs["sources"].items()}}


def main(argv=None, now=None):
    # unwind on SIGTERM and at the deadline, so an unpublished run directory or temp file is removed
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    signal.signal(signal.SIGALRM, lambda *_: sys.exit(f"kaizen: run passed its {args.deadline}s deadline"))
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", nargs="?", default="run", choices=("run", "baseline", "adopt", "resolve"))
    p.add_argument("change", nargs="?", help="baseline: the change id; adopt: the commit")
    p.add_argument("--home", type=Path, default=Path.home())
    p.add_argument("--watch-file", default=str(HERE / "watch.json"))
    p.add_argument("--gh", default="gh")
    p.add_argument("--chezmoi", default="chezmoi")
    p.add_argument("--launchctl", default="launchctl")
    p.add_argument("--no-gh", action="store_true")
    p.add_argument("--no-t3", action="store_true")
    p.add_argument("--no-apply", action="store_true", help="skip the apply stage")
    p.add_argument("--yes", action="store_true", help="resolve: clear the journal")
    p.add_argument("--deadline", type=int, default=DEADLINE, help="seconds before the run exits; a run already publishing finishes that first")
    args = p.parse_args(argv)
    signal.alarm(args.deadline)
    try:
        run_command(p, args, now)
    finally:
        signal.alarm(0)


def run_command(p, args, now):
    home = args.home.expanduser()
    k = Path(os.environ.get("KAIZEN_HOME") or home / ".claude/kaizen").expanduser()
    now = now or datetime.now(timezone.utc)
    if args.command == "baseline":
        if not args.change:
            p.error("baseline needs a change id")
        summary = baseline(k, home / ".claude/projects", args.watch_file, args.change, now)
    elif args.command == "adopt":
        if not args.change:
            p.error("adopt needs a commit")
        try:
            summary = apply.adopt(home, ready.source_repo(args.chezmoi), args.change)
        except apply.ApplyError as e:
            raise SystemExit(f"kaizen: adopt: {e}") from e
    elif args.command == "resolve":
        try:
            summary = apply.resolve(home, args.yes)
        except apply.ApplyError as e:
            raise SystemExit(f"kaizen: resolve: {e}") from e
    else:
        summary = run_cycle(k, home, now, args)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
