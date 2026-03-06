# skills

Standalone project for skill source, build tooling, and validation.

## Layout

- `src/`
  - Source of truth for editable skills.
  - `src/<skill>/` contains each skill's `SKILL.md`, `references/`, `scripts/`, and optional `tests/`.
  - Structured reference sections may use `*.md.j2` + adjacent `*.fragments.json`; build renders them back to plain Markdown artifacts.
  - `src/common/` contains shared source-only helpers vendored into built artifacts.
- `scripts/`
  - Build/install/reconcile helpers used by `Makefile`.
- `tests/`
  - Cross-skill tests for the build pipeline and artifact validation.
- `pyproject.toml`
  - Local Python project config for `uv`, `pytest`, `pydantic`, and `Jinja2`.
- `Makefile`
  - Entrypoints for build, test, install, reconcile, audit, and sync.

## Commands

- `make -C skills build`
  - Build `../etc/claude/skills/**` from `src/**`.
- `make -C skills test`
  - Run pytest for `src/**` and `tests/**`.
- `make -C skills fmt`
  - Run `ruff format` for Python files in `src/**`, `tests/**`, and `scripts/**`.
- `make -C skills lint`
  - Run `ruff check` for Python files in `src/**`, `tests/**`, and `scripts/**`.
- `make -C skills sync`
  - Build artifacts, install managed skills, reconcile stale managed skills, audit Codex duplicates, and sync `AGENTS.md`.

## Notes

- `../etc/claude/skills/**` is the committed artifact tree. Do not edit it by hand.
- `src/common/` and `tests/` are project internals, not skills.
