# dotfiles

I am the bone of my dotfiles.

## Install

```bash
git clone https://github.com/shuymn/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
make install-nix
make apply
make switch
make mise
```

`make switch` applies the nix-darwin system profile and the embedded Home Manager profile. It generates ignored `nix/local.nix` from `nix/local.nix.tmpl` before switching, so user name, home directory, host name, and ComputerName stay out of tracked Nix files.

Nix/Home Manager activation is intentionally single-path: use `make switch`, which runs `darwin-rebuild switch` with the embedded Home Manager module. Do not run a separate standalone `home-manager switch` for this repo.

On the first nix-darwin activation, if `/etc/bashrc` or `/etc/zshrc` blocks activation, back them up and retry:

```bash
sudo mv /etc/bashrc /etc/bashrc.before-nix-darwin
sudo mv /etc/zshrc /etc/zshrc.before-nix-darwin
make switch
```

## Daily commands

```bash
make check      # validate the flake
make build      # build the nix-darwin profile without switching
make switch     # apply nix-darwin + Home Manager
make apply      # apply chezmoi-managed dotfile links
make mise       # install mise-managed global tools
make check-brew # check Homebrew against nix-darwin's generated Brewfile
make audit-cli-path # list non-Nix/non-mise PATH executables to classify
make agents     # link/sync Claude, Codex, and pi agent files
```

## Ownership

- Nix/Home Manager: daily CLI tools, shell-owned user packages, and `mise`.
- nix-darwin: macOS settings, Nix daemon settings, shell enablement, Homebrew taps, tap-only formulae, and GUI casks.
- mise: language runtimes and pinned tool backends in `.config/mise/config.toml` plus `.config/mise/mise.lock`.
- chezmoi: tracked dotfiles under `home/`, including `.config` entries as normal chezmoi source state.

Homebrew is intentionally limited to GUI casks and tap-only formulae that are not in nixpkgs. `make switch` is the only Homebrew reconciliation path; do not keep or run a parallel Brewfile.

Put daily interactive CLIs and editor-facing development tools in Nix/Home Manager. Put version-switched runtimes and pinned helper CLIs in mise. Use mise backends directly instead of maintaining separate global aqua, npm, pipx, cargo, or uv tool layers.

Do not use global `cargo install`, `npm install -g`, `pipx install`, or `uv tool install` as managed CLI layers. Prefer mise backends for versioned global tools and project-local environments for repo-specific tools.

Existing mise `npm:` and `pipx:` global tools are retained for now, but treat new additions through those backends as exceptions that require an explicit reason.

`~/.config` should be a normal directory. Do not symlink the whole directory back to this repo; keep application state and generated files outside git, and manage only intentional dotfiles through `home/dot_config/**`.

## Agent files

`make agents` links Claude and pi files, installs skills, and syncs `etc/claude/CLAUDE.md` to `~/.codex/AGENTS.md`.

# License

MIT
