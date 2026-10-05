# Ownership checks: Home Manager stays inside nix/ownership.nix for every role,
# and chezmoi never manages a path Home Manager may write.
{
  lib,
  pkgs,
  roles,
  homeConfigurationFor,
}:

let
  ownership = import ./ownership.nix;

  roleCheck =
    role:
    let
      home = homeConfigurationFor role;
      files = map (file: file.target) (lib.filter (file: file.enable) (lib.attrValues home.home.file));
      unexpected = {
        files = lib.subtractLists ownership.homeFiles files;
        activation = lib.subtractLists ownership.activation (lib.attrNames home.home.activation);
      };
    in
    if unexpected.files == [ ] && unexpected.activation == [ ] then
      pkgs.runCommand "home-manager-ownership-${role}" { } "touch $out"
    else
      throw "Home Manager role '${role}' owns targets missing from nix/ownership.nix: ${builtins.toJSON unexpected}";

  chezmoiCollision =
    pkgs.runCommand "chezmoi-home-manager-collision"
      {
        nativeBuildInputs = [ pkgs.chezmoi ];
        homeManagerTargets = lib.concatLines ownership.homeFiles;
        passAsFile = [ "homeManagerTargets" ];
      }
      ''
        export HOME="$TMPDIR/home"
        printf '[data]\nhomeProfiles = []\n' > "$TMPDIR/chezmoi.toml"
        chezmoi --config "$TMPDIR/chezmoi.toml" --source ${../home} --destination "$TMPDIR/dest" \
          --persistent-state "$TMPDIR/chezmoistate.boltdb" \
          managed --include files,symlinks --path-style relative > managed
        collisions=$(awk 'NR == FNR { owned[$0] = 1; next }
          { for (target in owned) if ($0 == target || index($0, target "/") == 1) print }' \
          "$homeManagerTargetsPath" managed)
        if [ -n "$collisions" ]; then
          printf 'chezmoi manages paths owned by Home Manager:\n%s\n' "$collisions" >&2
          exit 1
        fi
        touch $out
      '';
in
lib.mapAttrs' (role: _: lib.nameValuePair "home-manager-ownership-${role}" (roleCheck role)) roles
// {
  chezmoi-home-manager-collision = chezmoiCollision;
}
