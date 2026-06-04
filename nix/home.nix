{ pkgs, localConfig, ... }:

let
  aqua = pkgs.callPackage ./packages/aqua.nix { };
  pi-coding-agent = pkgs.callPackage ./packages/pi-coding-agent.nix { };
in
{
  home.username = localConfig.username;
  home.homeDirectory = localConfig.homeDirectory;
  home.stateVersion = "26.05";

  programs.home-manager.enable = true;

  home.packages = with pkgs; [
    _1password-cli
    age
    aqua
    atuin
    bash
    bat
    beads
    cargo-binstall
    cargo-cache
    cargo-nextest
    cargo-update
    chezmoi
    claude-code
    cloudflared
    cmake
    curl
    delta
    direnv
    eza
    fd
    fzf
    gdu
    gh
    ghq
    git
    git-secrets
    gnused
    go-licenses
    go-task
    golangci-lint
    gopls
    goreleaser
    gotools
    govulncheck
    helix
    jq
    mise
    mo
    moq
    neovim
    opencode
    pi-coding-agent
    pre-commit
    ripgrep
    rustup
    sd
    semgrep
    sops
    sqlmap
    tart
    tmux
    vhs
    vim
    wget
    yamllint
    yq
    zoxide
    zsh-completions
    zsh-fast-syntax-highlighting
  ];
}
