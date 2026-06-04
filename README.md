# dotfiles

I am the bone of my dotfiles.

## Install

```bash
git clone https://github.com/shuymn/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
make install-nix
make apply
make switch
```

`make switch` applies the nix-darwin system profile and the embedded Home Manager profile. It generates ignored `nix/local.nix` from `nix/local.nix.tmpl` before switching, so user name, home directory, host name, and ComputerName stay out of tracked Nix files.

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
make agents     # link/sync Claude, Codex, and pi agent files
```

## Ownership

- Nix/Home Manager: base CLI tools, `mise`, `aqua`, and `pi`.
- nix-darwin: macOS settings, Nix daemon settings, shell enablement, Homebrew taps, tap-only formulae, and GUI casks.
- mise: runtimes in `.config/mise/config.toml`.
- aqua: pinned CI/release helper CLIs in `.config/aqua/aqua.yaml`.
- chezmoi: dotfile links from `home/`.

Homebrew is intentionally limited to GUI casks and tap-only formulae that are not in nixpkgs. `.Brewfile` mirrors the nix-darwin Homebrew module as an inventory fallback; do not run `brew bundle` and `make switch` as competing reconciliation commands.

## Agent files

`make agents` links Claude and pi files, installs skills, and syncs `etc/claude/CLAUDE.md` to `~/.codex/AGENTS.md`.

## Cargo tools

```bash
awk '/^[a-z]/ {print $1}' ./etc/cargo/cargo-installed.txt | xargs cargo install --locked
```

# License

MIT
