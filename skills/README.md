# skills

Standalone project for skill source, build tooling, and validation.

## Layout

- `src/`
  - Source of truth for editable skills.
  - `src/<skill>/` contains each skill's `SKILL.md`, `references/`, `scripts/`, and optional `tests/`.
  - `src/common/` contains shared source-only helpers vendored into built artifacts.
- `scripts/`
  - Build/install/reconcile helpers used by `Makefile`.
- `tests/`
  - Cross-skill tests for the build pipeline and artifact validation.
- `pyproject.toml`
  - Local Python project config for `uv` and `pytest`.
- `Makefile`
  - Entrypoints for build, test, install, reconcile, audit, and sync.

## Commands

- `make -C skills build`
  - Build `../etc/claude/skills/**` from `src/**`.
- `make -C skills test`
  - Run pytest for `src/**` and `tests/**`.
- `make -C skills sync`
  - Build artifacts, install managed skills, reconcile stale managed skills, audit Codex duplicates, and sync `AGENTS.md`.

## Notes

- `../etc/claude/skills/**` is the committed artifact tree. Do not edit it by hand.
- `src/common/` and `tests/` are project internals, not skills.
