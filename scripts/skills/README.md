# skills scripts

Helper scripts for the `make skills-*` workflow.

## Files

- `skills_manifest_refresh.py`
  - Scans `etc/claude/skills` and updates the managed manifest.
  - Output: `etc/claude/skills/.dotfiles-managed-skills.json`.
- `skills_mark_managed.py`
  - Writes `.dotfiles-managed` markers to installed managed skills.
- `skills_reconcile.py`
  - Removes stale managed skills only (`managed_installed - manifest.skills`).
  - External skills without marker are preserved.
- `sync_shared.py`
  - Syncs `_shared` assets into `~/.agents/skills/_shared`.
  - Uses mirror mode (`--delete`) in `make skills-sync-shared`.
- `audit_codex_skills.py`
  - Audits `~/.codex/skills` and detects entries duplicated in `~/.agents/skills`.
  - In `make skills-audit-codex`, duplicate entries are pruned from `~/.codex/skills`.
  - Codex-only entries are preserved.

## Usage

Use Make targets instead of calling scripts directly:

- `make skills-manifest-refresh`
- `make skills-install`
- `make skills-reconcile`
- `make skills-sync-shared`
- `make skills-audit-codex`
- `make skills-sync`

## Runtime requirements

- `uv` for Python execution
- `bun` and `bunx` for `skills` CLI execution
