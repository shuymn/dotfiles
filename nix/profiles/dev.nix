{ pkgs, ... }:

{
  home.packages = with pkgs; [
    beads
    ghq
    golangci-lint
    gopls
    gotools
    govulncheck
    mo
    pre-commit
    rustup
    shellcheck
    shfmt
    yamllint
  ];
}
