{ pkgs, ... }:

{
  home.packages = with pkgs; [
    _1password-cli
    claude-code
    opencode
    semgrep
    sops
    sqlmap
  ];
}
