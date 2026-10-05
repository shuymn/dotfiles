<!-- Keep durable repository constraints here. Update the relevant section when ownership or workflow boundaries change. -->

# AGENTS.md

`CLAUDE.md` links to this file. Shared home-level instructions are managed in `home/dot_claude/CLAUDE.md`; Codex and pi use links to its deployed copy. Edit the source, not the copies.

## Repo-Specific Rules

### Local Data and Activation

- Keep host-specific Nix values out of commits: generate ignored `nix/local.nix` from `nix/local.nix.tmpl` via chezmoi data; keep `nix/local.default.nix` generic. Never commit real usernames, home directories, host names, or ComputerName values.
- Keep shared Git behavior in `home/dot_gitconfig`; identity, signing keys, allowed signers, and machine IDs belong in ignored local files under `~/.config/git/`.
- Keep chezmoi age encryption enabled in root `.chezmoi.toml.tmpl`. Never manage or commit `~/.config/age/key.txt`; back it up out-of-band.
- Activate Nix/Home Manager only through nix-darwin. Prefer `make switch`, which regenerates local config; do not add standalone `homeConfigurations` or recommend `home-manager switch` unless non-Darwin support is requested.
- Run `chezmoi apply` only when applying to the live home directory is intended; source edits alone do not imply activation.

### Configuration Ownership

- Keep dotfile target state under `home/**` and Home Manager limited to environment declarations. Do not add `home.file`, `xdg.*File`, or file-writing `home.activation` for chezmoi-owned targets; migrate ownership in one direction and remove the other writer in the same change.
- Put daily interactive CLI groups in `nix/home/profiles/*.nix`, compose through `nix/home/roles/*.nix`, and keep Home Manager wiring in `nix/home/default.nix`. Keep macOS base settings in `nix/darwin/profiles/common.nix`; compose role-specific Homebrew packages through Darwin profiles and roles.
- Declare Nix daemon/client settings via `nix.settings` in `nix/darwin/profiles/common.nix`, not `home/dot_config/nix/nix.conf`.
- Keep chezmoi source state inside `home/**`; do not point managed targets back to repo-root dotfiles with symlink templates. Preserve root `.chezmoi.toml.tmpl` and `make chezmoi-config` so plain chezmoi commands use this checkout after bootstrap.
- Keep root-template helpers under `scripts/**` bootstrap-safe: invoke through `/bin/sh`, use POSIX sh unless the caller explicitly selects another shell, and do not require executable bits for rendering.

### Package and Editor Changes

- Use mise for version-switched runtimes and pinned helper CLIs. Prefer `mise install`; existing `npm:`/`pipx:` entries may remain, but new global `npm:`/`pipx:`/`cargo:`/`go:`/`gem:` entries need an explicit exception reason.
- For Zed, keep the app cask in Darwin profiles, settings/keymaps in `home/dot_config/zed/**`, and LSP/formatter binaries in Home Manager profiles. Render extension lists using chezmoi's `nixRole`; retain extensions that fetch tools only when pinned to local Nix/project binaries. Do not enable Home Manager Zed settings without migrating config ownership away from chezmoi in the same change.

### Renovate and mise Updates

- Pin Hosted Renovate compatibility validation through `.github/renovate-version`; do not reintroduce self-hosting solely to pin Renovate.
- Keep Renovate's mise manager disabled. `.github/workflows/mise-update.yml` is the only automated writer of `home/dot_config/mise/{config.toml,mise.lock}`; its selection rules and trust boundary are in `docs/mise-update.md`.
- Keep its three trust zones: `generate` runs upstream installers with read-only permissions and its outputs and artifacts are untrusted; `verify` checks the candidate without credentials; only `publish` holds the maintainer App token (current repository, contents and pull-requests write) and it runs only GitHub API calls and scripts from `github.sha`. Check out `github.sha` in `verify` and `publish`, never a ref reported by `generate`.
- Never expose that App secret/token to `pull_request` workflows, force-update a branch, or let Renovate run mise through `allowedUnsafeExecutions`/`postUpgradeTasks`.

### Change-Specific Validation

| Change | Required check or reference |
| --- | --- |
| Migrating unmanaged global CLIs | Run `make audit-cli-path` first; use PATH evidence to choose ownership. |
| Adding or renaming mise tools | Update `mise.lock` with `mise lock`, then run `make check-mise-updates`; every tool must report release timestamps, or `mise-update.yml` fails (see `docs/mise-update.md`). |
| Homebrew taps, formulae, or casks | Run `make check-brew` to check availability and compare installed formula leaves/casks with the generated Brewfile. |
| Nix or activation paths | Run `make check`, including generated local config and ownership checks. |
| Chezmoi source state | Run `chezmoi diff`; inspect the intended home-directory changes without applying them. |

### Documentation

- Keep `README.md` a user-facing current-state overview, not an exhaustive mirror of discoverable code/config details.

<!-- Maintenance: Update this file when skill or dotfile ownership changes. -->
