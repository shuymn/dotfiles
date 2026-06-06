{ lib, ... }:

let
  workspaceKeys = map (workspaceNumber: {
    key = if workspaceNumber == 10 then "0" else toString workspaceNumber;
    workspace = toString workspaceNumber;
  }) (lib.range 1 10);

  optimisticWorkspaceCommand =
    workspace: action:
    ''exec-and-forget /bin/sh -c "$HOME/.config/sketchybar/plugins/aerospace_workspace.sh optimistic ${workspace} ${action}"'';

  workspaceBindings = builtins.listToAttrs (
    (map (item: {
      name = "alt-${item.key}";
      value = [
        (optimisticWorkspaceCommand item.workspace "focus")
        "workspace ${item.workspace}"
      ];
    }) workspaceKeys)
    ++ (map (item: {
      name = "alt-shift-${item.key}";
      value = [
        (optimisticWorkspaceCommand item.workspace "move")
        "move-node-to-workspace ${item.workspace}"
        "workspace ${item.workspace}"
      ];
    }) workspaceKeys)
  );

  aerospaceSettings = lib.recursiveUpdate (lib.importTOML ../aerospace.toml) {
    mode.main.binding = workspaceBindings;
  };
in
{
  homebrew = {
    taps = [
      "songmu/tap"
      "xdevplatform/tap"
    ];

    brews = [
      "songmu/tap/maltmill"
    ];

    casks = [
      "choosy"
      "orbstack"
      "tailscale-app"
      "xdevplatform/tap/xurl"
    ];
  };

  services = {
    aerospace = {
      enable = true;
      settings = aerospaceSettings;
    };

    sketchybar.enable = true;

    jankyborders = {
      enable = true;
      width = 2.0;
      hidpi = true;
      active_color = "0x66c9d1d9";
      inactive_color = "0x0030363d";
      style = "round";
      order = "above";
    };
  };
}
