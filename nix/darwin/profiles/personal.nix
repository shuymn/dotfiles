{ lib, localConfig, pkgs, ... }:

let
  baseAerospaceSettings = lib.importTOML ../aerospace.toml;
  spindlePackage = pkgs.spindle;
  spindleBin = lib.getExe spindlePackage;
  spindleSketchybarBin = lib.getExe' spindlePackage "spindle-sketchybar";
  jqBin = lib.getExe pkgs.jq;
  spindleShare = "${spindlePackage}/share/spindle";
  spindleStateDir = "${localConfig.homeDirectory}/.local/state/spindle";
  spindleEmit = "${localConfig.homeDirectory}/.config/spindle/emit.sh";

  workspaceKeys = map (workspace: {
    key = if workspace == "10" then "0" else workspace;
    inherit workspace;
  }) baseAerospaceSettings.persistent-workspaces;

  workspaceBindings = builtins.listToAttrs (
    (map (item: {
      name = "alt-${item.key}";
      value = "workspace ${item.workspace}";
    }) workspaceKeys)
    ++ (map (item: {
      name = "alt-shift-${item.key}";
      value = [
        "move-node-to-workspace ${item.workspace}"
        "workspace ${item.workspace}"
      ];
    }) workspaceKeys)
  );

  aerospaceKeys = [
    "a"
    "b"
    "c"
    "d"
    "e"
    "f"
    "g"
    "h"
    "i"
    "j"
    "k"
    "l"
    "m"
    "n"
    "o"
    "p"
    "q"
    "r"
    "s"
    "t"
    "u"
    "v"
    "w"
    "x"
    "y"
    "z"
  ]
  ++ map toString (lib.range 0 9)
  ++ map (number: "keypad${toString number}") (lib.range 0 9)
  ++ map (number: "f${toString number}") (lib.range 1 20)
  ++ [
    "minus"
    "equal"
    "period"
    "comma"
    "slash"
    "backslash"
    "quote"
    "semicolon"
    "backtick"
    "leftSquareBracket"
    "rightSquareBracket"
    "space"
    "enter"
    "esc"
    "backspace"
    "tab"
    "pageUp"
    "pageDown"
    "home"
    "end"
    "forwardDelete"
    "sectionSign"
    "keypadClear"
    "keypadDecimalMark"
    "keypadDivide"
    "keypadEnter"
    "keypadEqual"
    "keypadMinus"
    "keypadMultiply"
    "keypadPlus"
    "left"
    "down"
    "up"
    "right"
  ];

  modifierSets =
    let
      modifiers = [
        "cmd"
        "alt"
        "ctrl"
        "shift"
      ];
      combinations =
        remaining:
        if remaining == [ ] then
          [ [ ] ]
        else
          let
            first = builtins.head remaining;
            restCombinations = combinations (builtins.tail remaining);
          in
          restCombinations ++ map (combination: [ first ] ++ combination) restCombinations;
    in
    map (combination: lib.concatStringsSep "-" combination) (combinations modifiers);

  modifiedAerospaceKeys = lib.flatten (
    map (
      modifierSet: map (key: if modifierSet == "" then key else "${modifierSet}-${key}") aerospaceKeys
    ) modifierSets
  );

  swallowBindingsFor = mode: lib.genAttrs modifiedAerospaceKeys (_: "mode ${mode}");

  nonMainModeBindings =
    mode: (swallowBindingsFor mode) // (baseAerospaceSettings.mode.${mode}.binding or { });

  nonMainModeOverrides =
    lib.genAttrs
      (builtins.filter (mode: mode != "main") (builtins.attrNames baseAerospaceSettings.mode))
      (mode: {
        binding = nonMainModeBindings mode;
      });

  aerospaceSettings = lib.recursiveUpdate baseAerospaceSettings {
    exec.env-vars = {
      JQ_BIN = jqBin;
      SPINDLE_BIN = spindleBin;
      SPINDLE_EMIT = spindleEmit;
      SPINDLE_STATE_DIR = spindleStateDir;
    };
    mode = nonMainModeOverrides // {
      main.binding = workspaceBindings;
    };
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
      "discord"
      "obsidian"
      "xdevplatform/tap/xurl"
      "zotero"
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

  launchd.user.agents.spindle.serviceConfig = {
    EnvironmentVariables = {
      SPINDLE_STATE_DIR = spindleStateDir;
      SPINDLE_SKETCHYBAR_STATE_DIR = spindleStateDir;
    };
    ProgramArguments = [
      "/bin/sh"
      "-c"
      ''
        set -eu
        spindle_state_dir=$1
        spindle_share=$2

        umask 077

        export SPINDLE_STATE_DIR="$spindle_state_dir"
        export SPINDLE_SKETCHYBAR_STATE_DIR="$spindle_state_dir"

        ${lib.escapeShellArg spindleBin} --state-dir "$spindle_state_dir" bootstrap \
          --extension-dir "$spindle_share/extensions" \
          --trust-runtime

        exec ${lib.escapeShellArg spindleBin} --state-dir "$spindle_state_dir" daemon
      ''
      "spindle-daemon"
      spindleStateDir
      spindleShare
    ];
    RunAtLoad = true;
    KeepAlive = true;
    StandardOutPath = "${localConfig.homeDirectory}/Library/Logs/spindle.out.log";
    StandardErrorPath = "${localConfig.homeDirectory}/Library/Logs/spindle.err.log";
  };

  launchd.user.agents.sketchybar.serviceConfig.EnvironmentVariables = {
    SPINDLE_BIN = spindleBin;
    SPINDLE_SKETCHYBAR_BIN = spindleSketchybarBin;
    SPINDLE_STATE_DIR = spindleStateDir;
  };

  system.activationScripts.postActivation.text = lib.mkAfter ''
    spindle_user_uid="$(${lib.getExe' pkgs.coreutils "id"} -u ${lib.escapeShellArg localConfig.username} 2>/dev/null || true)"
    if [ -n "$spindle_user_uid" ]; then
      /bin/launchctl asuser "$spindle_user_uid" /bin/launchctl kickstart -k "gui/$spindle_user_uid/org.nixos.spindle" || true
      # shellcheck source=/dev/null
      . ${lib.escapeShellArg "${localConfig.homeDirectory}/.config/spindle/lib-path.sh"}
      wait_for_spindle_socket ${lib.escapeShellArg "${spindleStateDir}/spindle.sock"} || true
      /bin/launchctl asuser "$spindle_user_uid" /bin/launchctl kickstart -k "gui/$spindle_user_uid/org.nixos.sketchybar" || true
    fi
  '';
}
