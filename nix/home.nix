{ pkgs, localConfig, ... }:

{
  home.username = localConfig.username;
  home.homeDirectory = localConfig.homeDirectory;
  home.stateVersion = "26.05";

  programs.home-manager.enable = true;

  home.packages = with pkgs; [
    _1password-cli
    age
    atuin
    bash
    bat
    beads
    chezmoi
    claude-code
    curl
    delta
    direnv
    eza
    fd
    fzf
    gh
    ghq
    git
    gnused
    golangci-lint
    gopls
    gotools
    govulncheck
    helix
    jq
    mise
    mo
    neovim
    opencode
    pre-commit
    ripgrep
    rustup
    semgrep
    shellcheck
    shfmt
    sops
    sqlmap
    tmux
    vim
    yamllint
    yq
    zoxide
    zsh-completions
    zsh-fast-syntax-highlighting
  ];
}
