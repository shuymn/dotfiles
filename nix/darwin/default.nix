{ localConfig, ... }:

let
  role = localConfig.role or "minimal";
  roleModule = ./roles + "/${role}.nix";
in
{
  imports = [
    ./profiles/common.nix
    (if builtins.pathExists roleModule then roleModule else throw "Unknown Darwin role '${role}'")
  ];
}
