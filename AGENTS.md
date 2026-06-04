<!-- Do not restructure or delete sections. Update inline when behavior changes. -->

# AGENTS.md

## Repo-Specific Rules

- Edit skills directly under `etc/claude/skills/**`; there is no separate `skills/` source tree.
- After changing skills, check for whitespace/conflict markers with `git diff --check -- etc/claude/skills`, then run `make sync-skills` to install them.
- Use `make link-claude` when you need to refresh `~/.claude/**` symlinks from this repo.
- Treat `README.md` as user-facing setup docs; keep this file limited to agent-only repository rules.
- Keep Nix/Home Manager activation single-path through `make switch`; do not add standalone `homeConfigurations` or recommend `home-manager switch` unless non-Darwin support is explicitly requested.
- Manage daily interactive CLIs in `nix/home.nix`, macOS settings and Homebrew casks/tap-only formulae in `nix/darwin.nix`, and dotfile target state under `home/**`.
- Keep mise for version-switched runtimes and pinned helper CLIs. Existing `npm:` and `pipx:` entries may remain, but new global `npm:`/`pipx:`/`cargo:`/`go:`/`gem:` tool entries need an explicit exception reason.
- Run `make audit-cli-path` before migrating unmanaged global CLIs so PATH-derived evidence drives the move.
- After Nix or activation-path changes, run `make check`. After chezmoi source-state changes, run `make apply` only when applying to the live home directory is intended.

<!-- Maintenance: Update this file when skill source/build ownership or Claude sync workflow changes. -->
