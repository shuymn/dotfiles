{ pkgs, ... }:

{
  home.packages = with pkgs; [
    age
    atuin
    bash
    bat
    chezmoi
    curl
    delta
    direnv
    eza
    fd
    fzf
    gh
    git
    gnused
    helix
    jq
    mise
    neovim
    ripgrep
    tmux
    vim
    yq
    zoxide
    zsh-completions
    zsh-fast-syntax-highlighting
  ];
}
