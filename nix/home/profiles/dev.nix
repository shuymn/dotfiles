{ pkgs, ... }:

{
  home.packages = with pkgs; [
    agent-browser
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
