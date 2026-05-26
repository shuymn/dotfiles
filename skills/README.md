# skills

Skill sources and install tooling.

## Layout

- `src/`
  - Source of truth for editable skills.
  - `src/<skill>/` contains each skill's `SKILL.md` and optional `references/`, `scripts/`, `tests/`.
- `Makefile`
  - Entrypoints for install and Codex `AGENTS.md` sync.

## Commands

- `make -C skills install`
  - Install skills from `../etc/claude/skills/**` via the `skills` CLI.
- `make -C skills sync`
  - Install skills and sync `AGENTS.md` for Codex.

## Notes

- `../etc/claude/skills/**` is the committed artifact tree consumed by `bunx skills add`.
- Edit `src/<skill>/SKILL.md` first; copy changes to the artifact tree when ready.
