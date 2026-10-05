{ localConfig, ... }:

let
  role = localConfig.role;
  roles = builtins.fromTOML (builtins.readFile ../roles.toml);
  profiles = roles.${role}.darwin or (throw "Unknown role '${role}' in host.toml");
in
{
  imports = [ ./profiles/common.nix ] ++ map (profile: ./profiles + "/${profile}.nix") profiles;
}
