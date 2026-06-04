<!-- Do not restructure or delete sections. Update inline when behavior changes. -->

# AGENTS.md

## Repo-Specific Rules

- Edit skills directly under `etc/claude/skills/**`; there is no separate `skills/` source tree.
- After changing skills, check for whitespace/conflict markers with `git diff --check -- etc/claude/skills`, then run `make sync-skills` to install them.
- Use `make link-claude` when you need to refresh `~/.claude/**` symlinks from this repo.
- Treat `README.md` as user-facing setup docs; keep this file limited to agent-only repository rules.
- Keep Nix/Home Manager activation single-path through nix-darwin; prefer `make switch` so ignored `nix/local.nix` is regenerated before activation. Do not add standalone `homeConfigurations` or recommend `home-manager switch` unless non-Darwin support is explicitly requested.
- Keep host-specific Nix values out of commits: generate ignored `nix/local.nix` from `nix/local.nix.tmpl` via chezmoi data, keep tracked `nix/local.default.nix` generic, and do not commit real username, home directory, host name, or ComputerName.
- Manage daily interactive CLI package groups in `nix/profiles/*.nix`, compose them through `nix/roles/*.nix`, keep Home Manager wiring in `nix/home.nix`, macOS settings and Homebrew casks/tap-only formulae in `nix/darwin.nix`, and dotfile target state under `home/**`.
- Keep chezmoi source state inside `home/**`; do not add symlink templates that point managed targets back to repo-root dotfiles. Preserve root `.chezmoi.toml.tmpl` and `make chezmoi-config` so plain `chezmoi` commands use this checkout after bootstrap.
- Keep chezmoi age encryption enabled via root `.chezmoi.toml.tmpl`, but never manage or commit `~/.config/age/key.txt`; it is local-only and must be backed up out-of-band.
- Keep mise for version-switched runtimes and pinned helper CLIs. Prefer plain `mise install`; `make mise` is only a shortcut. Existing `npm:` and `pipx:` entries may remain, but new global `npm:`/`pipx:`/`cargo:`/`go:`/`gem:` tool entries need an explicit exception reason.
- Run `make audit-cli-path` before migrating unmanaged global CLIs so PATH-derived evidence drives the move.
- After Nix or activation-path changes, run `make check` so chezmoi-generated `nix/local.nix` is included. After chezmoi source-state changes, run `chezmoi diff`; run `chezmoi apply` only when applying to the live home directory is intended.

<!-- Maintenance: Update this file when skill source/build ownership or Claude sync workflow changes. -->
