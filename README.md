# dotfiles

I am the bone of my dotfiles.

# Installation

```bash
git clone https://github.com/shuymn/dotfiles.git ~/.dotfiles && ~/.dotfiles/install.sh
```

## Agent setup

For Claude-related setup, run **both** `link-claude` and `sync-skills`.
For pi extensions, run `link-pi`.

```bash
make link-claude
make sync-skills
make link-pi
```

- `make link-claude`
  - Symlinks `etc/claude/**` into `~/.claude/**` (excluding `etc/claude/skills/**`).
- `make sync-skills`
  - Installs skills from the canonical `etc/claude/skills/**` tree using `bunx --bun skills`.
  - Syncs `etc/claude/CLAUDE.md` to `~/.codex/AGENTS.md`.
- `make link-pi`
  - Symlinks `etc/pi/**` into `~/.pi/**`.
  - Installs pi extensions such as `/commit`.

## Install commands via Cargo

```bash
awk '/^[a-z]/ {print $1}' ./etc/cargo/cargo-installed.txt | xargs cargo install --locked
```

# License

MIT
