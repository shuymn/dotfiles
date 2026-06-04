{ localConfig, ... }:

let
  role = localConfig.role or "minimal";
  roleModule = ./roles + "/${role}.nix";
in
{
  imports = [
    ./profiles/common.nix
    (if builtins.pathExists roleModule then roleModule else throw "Unknown Nix role '${role}'")
  ];

  home.username = localConfig.username;
  home.homeDirectory = localConfig.homeDirectory;
  home.stateVersion = "26.05";

  programs.home-manager.enable = true;
}
