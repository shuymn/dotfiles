# skills

Standalone project for skill source, build tooling, and validation.

## Layout

- `src/`
  - Source of truth for editable skills.
  - `src/<skill>/` contains each skill's `SKILL.md`, `references/`, `scripts/`, and optional `tests/`.
  - Structured reference sections use `*.md.tmpl` + adjacent `*.fragments.json`; build renders them back to plain Markdown artifacts.
  - `src/common/` contains shared source-only helpers vendored into built artifacts.
- `tools/skit/`
  - Go-based CLIs: `skit` for authoring/review checks and `skitkit` for build/sync management. See [`tools/skit/README.md`](tools/skit/README.md).
- `Makefile`
  - Entrypoints for build, test, install, reconcile, audit, and sync.

## Commands

- `make -C skills build`
  - Build `../etc/claude/skills/**` from `src/**`.
- `make -C skills sync`
  - Build artifacts via `skitkit`, install managed skills, reconcile stale managed skills, audit Codex duplicates, and sync `AGENTS.md`.

## Notes

- `../etc/claude/skills/**` is the committed artifact tree. Do not edit it by hand.
- `src/common/` is a project internal, not a skill.
