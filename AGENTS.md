<!-- Keep durable repository constraints here. Update the relevant section when ownership or workflow boundaries change. -->

# AGENTS.md

`CLAUDE.md` links to this file. Shared home-level instructions are managed in `home/dot_claude/CLAUDE.md`; Codex and pi use links to its deployed copy. Edit the source, not the copies.

## Repo-Specific Rules

### Local Data and Activation

- Keep host-specific values in the git-ignored `host.toml` (created by `make host`), which both Nix and `.chezmoi.toml.tmpl` read; keep `nix/host.default.toml` generic. Evaluate the flake as `path:<checkout>`, as the Makefile does, because a `git+file` flake cannot see `host.toml`. Never commit real usernames, home directories, host names, or ComputerName values.
- Keep shared Git behavior in `home/dot_gitconfig`; identity, signing keys, allowed signers, and machine IDs belong in ignored local files under `~/.config/git/`.
- Keep chezmoi age encryption enabled in root `.chezmoi.toml.tmpl`. Never manage or commit `~/.config/age/key.txt`; back it up out-of-band.
- Activate Nix/Home Manager only through nix-darwin: `make switch`, or `make converge` to apply chezmoi, nix-darwin, and mise in order. Do not add standalone `homeConfigurations` or recommend `home-manager switch` unless non-Darwin support is requested.
- Run `chezmoi apply` only when applying to the live home directory is intended; source edits alone do not imply activation.

### Configuration Ownership

- Keep dotfile target state under `home/**` and Home Manager limited to environment declarations plus the targets and activation steps listed in `nix/ownership.nix`; `make check` rejects anything else for every role and any chezmoi target that collides with that list. Extending the list is an ownership migration: move one direction and remove the other writer in the same change.
- Put daily interactive CLI groups in `nix/home/profiles/*.nix` and role-specific Homebrew packages in `nix/darwin/profiles/*.nix`; compose both per role in `nix/roles.toml`, the single role table shared by nix-darwin, Home Manager, and chezmoi. Keep Home Manager wiring in `nix/home/default.nix` and macOS base settings in `nix/darwin/profiles/common.nix`.
- Declare Nix daemon/client settings via `nix.settings` in `nix/darwin/profiles/common.nix`, not `home/dot_config/nix/nix.conf`.
- Keep chezmoi source state inside `home/**`; do not point managed targets back to repo-root dotfiles with symlink templates. Preserve root `.chezmoi.toml.tmpl` and `make chezmoi-config` so plain chezmoi commands use this checkout after bootstrap; rerun `make chezmoi-config` after changing `host.toml`, `nix/roles.toml`, or the template, because chezmoi keeps the rendered data.
- Keep root-template helpers under `scripts/**` bootstrap-safe: invoke through `/bin/sh`, use POSIX sh unless the caller explicitly selects another shell, and do not require executable bits for rendering.

### Package and Editor Changes

- Use mise for version-switched runtimes and pinned helper CLIs. Prefer `mise install`; existing `npm:`/`pipx:` entries may remain, but new global `npm:`/`pipx:`/`cargo:`/`go:`/`gem:` entries need an explicit exception reason.
- For Zed, keep the app cask in Darwin profiles, settings/keymaps in `home/dot_config/zed/**`, and LSP/formatter binaries in Home Manager profiles. Gate role-specific extensions and LSP entries in `home/.chezmoitemplates/zed/*.jsonc` on chezmoi's `homeProfiles` data; retain extensions that fetch tools only when pinned to local Nix/project binaries. Do not enable Home Manager Zed settings without migrating config ownership away from chezmoi in the same change.

### Renovate and mise Updates

- Pin Hosted Renovate compatibility validation through `.github/renovate-version`; do not reintroduce self-hosting solely to pin Renovate.
- Keep Renovate's mise manager disabled. `home/dot_config/mise/config.toml` holds major-version ranges, and `.github/workflows/mise-update.yml` advances `mise.lock` with `mise lock --bump`; major updates are manual range edits (`docs/mise-update.md`).
- Keep that job free of tool installs and tool execution, because it also holds the maintainer App token (current repository, contents and pull-requests write). Never expose that App secret/token to `pull_request` workflows or let Renovate run mise through `allowedUnsafeExecutions`/`postUpgradeTasks`.

### Change-Specific Validation

| Change | Required check or reference |
| --- | --- |
| Migrating unmanaged global CLIs | Run `make audit-cli-path` first; use PATH evidence to choose ownership. |
| Adding or renaming mise tools | Write the tool as a major-version range (`node = "24"`) and run `mise lock` in `home/dot_config/mise`; see `docs/mise-update.md`. |
| Homebrew taps, formulae, or casks | Run `make check-brew` to check availability and compare installed formula leaves/casks with the generated Brewfile. |
| Nix or activation paths | Run `make check`; its flake checks evaluate Home Manager ownership for every role in `nix/roles.toml`. Run `make build` when the activated system changes. |
| Chezmoi source state | Run `chezmoi diff`; inspect the intended home-directory changes without applying them. |

### Documentation

- Keep `README.md` a user-facing current-state overview, not an exhaustive mirror of discoverable code/config details.

<!-- Maintenance: Update this file when skill or dotfile ownership changes. -->
