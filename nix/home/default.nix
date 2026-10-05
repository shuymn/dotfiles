{ capsule, localConfig, ... }:

let
  role = localConfig.role;
  roles = builtins.fromTOML (builtins.readFile ../roles.toml);
  profiles = roles.${role}.home or (throw "Unknown role '${role}' in host.toml");
in
{
  imports = [
    capsule.homeManagerModules.default
    ./profiles/common.nix
  ]
  ++ map (profile: ./profiles + "/${profile}.nix") profiles;

  home.username = localConfig.username;
  home.homeDirectory = localConfig.homeDirectory;
  home.stateVersion = "26.05";

  programs.home-manager.enable = true;
}
