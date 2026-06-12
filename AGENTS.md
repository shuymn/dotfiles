<!-- Do not restructure or delete sections. Update inline when behavior changes. -->

# AGENTS.md

## Repo-Specific Rules

- Treat `README.md` as a user-facing current-state overview, not an exhaustive mirror of code. Keep code/config as the source of truth for details that can be read directly, and avoid README updates that merely restate those internals.
- Keep Nix/Home Manager activation single-path through nix-darwin; prefer `make switch` so ignored `nix/local.nix` is regenerated before activation. Do not add standalone `homeConfigurations` or recommend `home-manager switch` unless non-Darwin support is explicitly requested.
- Keep host-specific Nix values out of commits: generate ignored `nix/local.nix` from `nix/local.nix.tmpl` via chezmoi data, keep tracked `nix/local.default.nix` generic, and do not commit real username, home directory, host name, or ComputerName.
- Manage daily interactive CLI package groups in `nix/home/profiles/*.nix`, compose them through `nix/home/roles/*.nix`, keep Home Manager wiring in `nix/home/default.nix`, keep macOS base settings in `nix/darwin/profiles/common.nix`, compose role-specific Homebrew taps/formulae/casks through `nix/darwin/roles/*.nix` and `nix/darwin/profiles/*.nix`, and keep dotfile target state under `home/**`.
- Keep Home Manager as environment declaration, not dotfile placement. Do not add `home.file`, `xdg.*File`, or file-writing `home.activation` logic while the target belongs under `home/**`; migrate ownership in one direction and delete the other writer in the same change.
- Keep Nix daemon/client settings in `nix/darwin/profiles/common.nix` through `nix.settings`; do not add `home/dot_config/nix/nix.conf` for normal flake behavior.
- Keep shared Git behavior in tracked `home/dot_gitconfig`; keep identity, signing keys, allowed signers, and machine IDs in ignored local files under `~/.config/git/`.
- Keep Zed split by ownership: GUI app cask in `nix/darwin/profiles/*.nix`, user settings/keymaps in `home/dot_config/zed/**`, and editor-facing LSP/formatter binaries in `nix/home/profiles/*.nix`. Render Zed extension lists from chezmoi templates using `nixRole`. Do not auto-install or keep Zed extensions that fetch their own LSP/tool binaries unless the setting pins them to local Nix/project binaries. Do not enable Home Manager Zed settings unless migrating Zed config ownership away from chezmoi in the same change.
- Keep chezmoi source state inside `home/**`; do not add symlink templates that point managed targets back to repo-root dotfiles. Preserve root `.chezmoi.toml.tmpl` and `make chezmoi-config` so plain `chezmoi` commands use this checkout after bootstrap.
- Keep root-template helper scripts under `scripts/**` bootstrap-safe: call them through `/bin/sh`, keep them POSIX-sh compatible unless the caller explicitly uses another shell, and do not require executable bits for template rendering.
- Keep chezmoi age encryption enabled via root `.chezmoi.toml.tmpl`, but never manage or commit `~/.config/age/key.txt`; it is local-only and must be backed up out-of-band.
- Keep mise for version-switched runtimes and pinned helper CLIs. Prefer plain `mise install`; `make mise` is only a shortcut. Existing `npm:` and `pipx:` entries may remain, but new global `npm:`/`pipx:`/`cargo:`/`go:`/`gem:` tool entries need an explicit exception reason.
- Run `make audit-cli-path` before migrating unmanaged global CLIs so PATH-derived evidence drives the move.
- After adding or renaming mise tools, run `make check-mise-renovate`; tools that resolve to Renovate datasources without `releaseTimestamp` (or unsupported/unknown Renovate paths) can stay pending forever under `minimumReleaseAge`. Fix per `docs/renovate-mise-release-age.md` (prefer a timestamped backend, else a regex custom manager plus disabled mise lookup).
- After Homebrew tap/formula/cask changes, run `make check-brew`; it checks dependency availability and compares formula leaves/casks against the nix-darwin generated Brewfile.
- After Nix or activation-path changes, run `make check` so chezmoi-generated `nix/local.nix` and ownership checks are included. After chezmoi source-state changes, run `chezmoi diff`; run `chezmoi apply` only when applying to the live home directory is intended.

<!-- Maintenance: Update this file when skill or dotfile ownership changes. -->
