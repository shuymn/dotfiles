{ pkgs, ... }:

{
  home.packages = with pkgs; [
    biome
    claude-code
    delta
    direnv
    ghq
    golangci-lint
    gopls
    gotools
    govulncheck
    mo
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
