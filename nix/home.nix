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
    age
    aqua
    atuin
    bash
    bat
    beads
    chezmoi
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
    go-task
    helix
    jq
    mise
    mo
    neovim
    pi-coding-agent
    ripgrep
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
