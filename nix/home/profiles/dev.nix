{ pkgs, ... }:

{
  home.packages = with pkgs; [
    biome
    delta
    direnv
    ghq
    golangci-lint
    gopls
    gotools
    govulncheck
    nixd
    nixfmt
    opencode
    pre-commit
    rustup
    semgrep
    shellcheck
    shfmt
    sops
    sqlmap
    vscode-langservers-extracted
    yamllint
  ];
}
