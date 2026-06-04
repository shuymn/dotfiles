# dotfiles

I am the bone of my dotfiles.

## Install

```bash
git clone https://github.com/shuymn/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
make install-nix
make apply NIX_ROLE=personal
make switch
mise install
```

`make` targets are bootstrap-safe wrappers. Nix targets generate ignored `nix/local.nix` from `nix/local.nix.tmpl` before evaluation, so username, home directory, host name, ComputerName, and selected role stay out of commits.

The first `make apply NIX_ROLE=personal` writes `~/.config/chezmoi/chezmoi.toml` from `.chezmoi.toml.tmpl` with this checkout as `sourceDir`, stores the selected `nixRole` in chezmoi data, and applies the managed dotfiles. Available roles are the files under `nix/roles/`. After that, plain `chezmoi diff`, `chezmoi apply`, and `chezmoi managed` use this repo without extra flags.

chezmoi encryption uses age. Restore `~/.config/age/key.txt` from an out-of-band backup when decrypting existing encrypted files, or run `make age-key` to create a new local identity before adding encrypted files. The age secret key is intentionally ignored by chezmoi and git.

Nix/Home Manager activation is intentionally single-path through nix-darwin: use `make switch` from this checkout so the local Nix config is regenerated before activation. Do not run a separate standalone `home-manager switch` for this repo.

On the first nix-darwin activation, if `/etc/bashrc` or `/etc/zshrc` blocks activation, back them up and retry:

```bash
sudo mv /etc/bashrc /etc/bashrc.before-nix-darwin
sudo mv /etc/zshrc /etc/zshrc.before-nix-darwin
make switch
```

## Daily commands

```bash
make check
make build
make switch
chezmoi diff
chezmoi apply
chezmoi managed
mise install
```

Useful shortcuts:

```bash
make local                         # regenerate ignored nix/local.nix from chezmoi data
make chezmoi-config NIX_ROLE=personal # set or refresh this machine's role
make age-key                       # create a local age identity and refresh chezmoi config
make check-brew                    # check Homebrew against nix-darwin's generated Brewfile
make check-ownership               # check Home Manager does not claim dotfile targets
make audit-cli-path                # classify non-Nix/non-mise PATH owners and shadows
make agents                        # apply agent dotfiles and runtime syncs
```

## Ownership

- Nix/Home Manager: daily CLI tools, shell-owned user packages, and `mise`; common packages live in `nix/profiles/common.nix`, optional groups in `nix/profiles/*.nix`, and roles in `nix/roles/*.nix`.
- nix-darwin: macOS settings, Nix daemon/client settings, shell enablement, Homebrew taps, tap-only formulae, and GUI casks.
- Nix host config: ignored `nix/local.nix` generated from `nix/local.nix.tmpl`; tracked `nix/local.default.nix` is only a generic fallback.
- mise: language runtimes and pinned tool backends in `.config/mise/config.toml` plus `.config/mise/mise.lock`.
- chezmoi: tracked dotfiles under `home/`, including `.config` entries as normal chezmoi source state.
- age: local chezmoi encryption identity at `~/.config/age/key.txt`; never tracked, back up out-of-band.

One target path has one writer. In this repo, Home Manager is the environment declaration layer: package groups, profile composition, Home Manager enablement, and shell-owned package availability. chezmoi is the dotfile placement layer: files that should appear in `$HOME`, including application config under `~/.config`.

Do not add Home Manager `home.file`, `xdg.*File`, or file-writing `home.activation` logic for targets that belong under `home/**`. If a target becomes simpler as a Home Manager module, migrate it fully in one change: remove or ignore the corresponding chezmoi source, add the Home Manager owner, and update this ownership section.

Keep Nix client settings in `nix/darwin.nix` through `nix.settings`; do not add a separate `home/dot_config/nix/nix.conf` for normal flake behavior.

Git is split the same way: shared behavior lives in `home/dot_gitconfig`, while identity, signing, allowed signers, and machine-specific CLI state stay in ignored local files under `~/.config/git/`. The tracked config includes `~/.config/git/config.local` at the end so local values can override shared defaults.

Homebrew is intentionally limited to GUI casks and tap-only formulae that are not in nixpkgs. nix-darwin activation is the only Homebrew reconciliation path; do not keep or run a parallel Brewfile.

Zed follows that split: the GUI app stays as a Homebrew cask in `nix/darwin.nix`, settings and keymaps live under `home/dot_config/zed/**`, and editor-facing tools such as `nixd` and `nixfmt` come from Nix/Home Manager. Zed loads `direnv` so project flake/dev shell environments can provide project-local toolchains. Zed extensions are rendered by chezmoi from `nixRole`: `personal` keeps the full interactive extension set, while other roles get the minimal Nix extension set. Avoid auto-installing or keeping Zed extensions that fetch their own LSP/tool binaries unless they are pinned to local Nix or project-provided binaries.

Put daily interactive CLIs and editor-facing development tools in Nix/Home Manager. Put version-switched runtimes and pinned helper CLIs in mise. Use mise backends directly instead of maintaining separate global aqua, npm, pipx, cargo, or uv tool layers.

Do not use global `cargo install`, `npm install -g`, `pipx install`, or `uv tool install` as managed CLI layers. Prefer mise backends for versioned global tools and project-local environments for repo-specific tools.

Existing mise `npm:` and `pipx:` global tools are retained for now, but treat new additions through those backends as exceptions that require an explicit reason.

`~/.config` should be a normal directory. Do not symlink the whole directory back to this repo; keep application state and generated files outside git, and manage only intentional dotfiles through `home/dot_config/**`.

chezmoi source state lives under `home/` via `.chezmoiroot`. Keep managed home files in that source state instead of symlinking targets back to repo-root files.

## Agent files

Static Claude, Codex, and pi agent dotfiles are managed by chezmoi under `home/dot_claude/**`, `home/dot_codex/**`, and `home/dot_pi/**`. `~/.codex/AGENTS.md` and `~/.pi/agent/AGENTS.md` are chezmoi-managed symlinks to `~/.claude/CLAUDE.md`.

`make agents` applies those agent dotfile targets, installs skills from `etc/claude/skills/**`, and runs `pi install` for the local pi extensions checkout when present.

# License

MIT
