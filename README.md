# dotfiles

I am the bone of my dotfiles.

# Installation

```bash
curl -fsSL https://raw.githubusercontent.com/shuymn/dotfiles/main/install.sh | bash
```

## Claude and Skills setup

For Claude-related setup, run **both** `link-claude` and `skills-sync`.

```bash
make link-claude
make skills-sync
```

- `make link-claude`
  - Symlinks `etc/claude/**` into `~/.claude/**` (excluding `etc/claude/skills/**`).
- `make skills-build`
  - Delegates to `skills/Makefile`.
  - Builds the committed artifact tree at `etc/claude/skills/**` from editable sources in `skills/src/**`.
- `make skills-test`
  - Delegates to `skills/Makefile`.
  - Runs pytest from the standalone `skills/` project (`skills/pyproject.toml`).
- `make skills-fmt`
  - Delegates to `skills/Makefile`.
  - Runs `ruff format` for Python files under `skills/src/**`, `skills/tests/**`, and `skills/scripts/**`.
- `make skills-lint`
  - Delegates to `skills/Makefile`.
  - Runs `ruff check` for Python files under `skills/src/**`, `skills/tests/**`, and `skills/scripts/**`.
- `make skills-sync`
  - Delegates to `skills/Makefile`.
  - Rebuilds `etc/claude/skills/**` from `skills/src/**` before installation.
  - Manages skills from `etc/claude/skills/**` using `bunx --bun skills`.
  - Reconciles stale managed skills while preserving external/manual skills.
  - Treats `~/.agents/skills` as canonical and prunes only duplicates from `~/.codex/skills`.
  - Syncs `etc/claude/CLAUDE.md` to `~/.codex/AGENTS.md`.

## Install commands via Cargo

```bash
awk '/^[a-z]/ {print $1}' ./etc/cargo/cargo-installed.txt | xargs cargo install --locked
```

# License

MIT
