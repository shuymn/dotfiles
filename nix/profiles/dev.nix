{ pkgs, ... }:

{
  home.packages = with pkgs; [
    astro-language-server
    beads
    biome
    ghq
    golangci-lint
    gopls
    gotools
    govulncheck
    mo
    nixd
    nixfmt
    pre-commit
    prisma-language-server
    rustup
    shellcheck
    shfmt
    vscode-langservers-extracted
    yamllint
  ];
}
