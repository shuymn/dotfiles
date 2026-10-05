{ pkgs, ... }:

{
  home.packages = with pkgs; [
    beads
  ];
}
