{ pkgs, ... }:

{
  home.packages = with pkgs; [
    astro-language-server
    beads
    prisma-language-server
    spindle
  ];
}
