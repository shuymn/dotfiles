{ pkgs, ... }:

let
  lspPackages = with pkgs; [
    basedpyright
    gopls
    lua-language-server
    nixd
    ruff
    taplo
    typescript
    typescript-language-server
    vscode-langservers-extracted
    yaml-language-server
  ];
in
{
  home.packages = with pkgs; [
    _1password-cli
    agent-browser
    bat
    biome
    direnv
    eza
    fd
    fzf
    ghq
    glimpseui
    gnused
    golangci-lint
    gotools
    govulncheck
    jq
    nix-direnv
    nixfmt
    pre-commit
    rustup
    semgrep
    shellcheck
    shfmt
    sops
    sqlmap
    tmux
    yamllint
    yazi
    yq
    zoxide
    zsh-completions
    zsh-fast-syntax-highlighting
  ] ++ lspPackages;

  programs.gh = {
    enable = true;
  };

  programs.gh-dash = {
    enable = true;
  };
}
