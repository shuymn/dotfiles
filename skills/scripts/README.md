# skills scripts

Helper scripts for the local `skills/Makefile` workflow.

## Files

- `build_skills.py`
  - Builds standalone artifacts from `src/**` into `../etc/claude/skills/**`.
  - Reads per-skill `skill.json` declarations and common install-path metadata to resolve common script dependencies.
  - Installs public helper entrypoints in `scripts/` and internal shared helpers in `scripts/lib/`.
  - Excludes `tests/`, `__pycache__/`, and other source-only files from artifacts.
  - Validates `SKILL.md` script references and forbids parent-traversal helper paths.
- `skills_manifest_refresh.py`
  - Shared helper used by `build_skills.py` to generate the managed manifest.
  - Scans a skills artifact tree and writes a machine-independent manifest.
- `skills_mark_managed.py`
  - Writes `.dotfiles-managed` markers to installed managed skills.
- `skills_reconcile.py`
  - Removes stale managed skills only (`managed_installed - manifest.skills`).
  - External skills without marker are preserved.
- `audit_codex_skills.py`
  - Audits `~/.codex/skills` and detects entries duplicated in `~/.agents/skills`.
  - In `make skills-audit-codex`, duplicate entries are pruned from `~/.codex/skills`.
  - Codex-only entries are preserved.

## Usage

Use Make targets instead of calling scripts directly:

- `make -C skills build`
- `make -C skills test`
- `make -C skills install`
- `make -C skills reconcile`
- `make -C skills audit-codex`
- `make -C skills sync`

## Runtime requirements

- `uv` for Python execution
- `pytest` via `uv run --group dev pytest` for skills validation
- `bun` and `bunx` for `skills` CLI execution
- `SKILLS_CMD` (`bunx --bun skills`) runs the latest published version of the `skills` CLI without a version pin. Behavior may change on upstream releases.
