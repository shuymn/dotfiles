# dotfiles

I am the bone of my dotfiles.

# Installation

```bash
curl -fsSL https://raw.githubusercontent.com/shuymn/dotfiles/main/install.sh | bash
```

## Claude and Skills setup

For Claude-related setup, run **both** `link-claude` and `sync-skills`.

```bash
make link-claude
make sync-skills
```

- `make link-claude`
  - Symlinks `etc/claude/**` into `~/.claude/**` (excluding `etc/claude/skills/**`).
- `make sync-skills`
  - Delegates to `skills/Makefile`.
  - Rebuilds `etc/claude/skills/**` from `skills/src/**` via `skitkit` before installation.
  - Manages skills from `etc/claude/skills/**` using `bunx --bun skills`.
  - Reconciles stale managed skills while preserving external/manual skills.
  - Treats `~/.agents/skills` as canonical and prunes only duplicates from `~/.codex/skills`.
  - Syncs `etc/claude/CLAUDE.md` to `~/.codex/AGENTS.md`.
- For local skills development commands such as build/test/fmt/lint, use `make -C skills ...`.

## Install commands via Cargo

```bash
awk '/^[a-z]/ {print $1}' ./etc/cargo/cargo-installed.txt | xargs cargo install --locked
```

# License

MIT
