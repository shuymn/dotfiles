{ pkgs, ... }:

{
  home.packages = with pkgs; [
    astro-language-server
    prisma-language-server
  ];
}
