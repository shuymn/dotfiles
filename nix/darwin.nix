{ lib, localConfig, ... }:

{
  system.stateVersion = 5;
  system.primaryUser = localConfig.username;

  nixpkgs.hostPlatform = localConfig.system;
  nixpkgs.config.allowUnfreePredicate = pkg: builtins.elem (lib.getName pkg) [ "tart" ];

  nix.settings = {
    experimental-features = [
      "nix-command"
      "flakes"
    ];
    trusted-users = [
      "root"
      localConfig.username
    ];
  };

  networking = {
    computerName = localConfig.computerName;
    hostName = localConfig.hostName;
    localHostName = localConfig.hostName;
  };

  users.users.${localConfig.username}.home = localConfig.homeDirectory;
  programs.zsh.enable = true;

  homebrew = {
    enable = true;

    onActivation = {
      autoUpdate = false;
      upgrade = false;
      cleanup = "none";
    };

    taps = [
      "coderabbitai/tap"
      "shuymn/tap"
      "songmu/tap"
      "xdevplatform/tap"
    ];

    brews = [
      "coderabbitai/tap/git-gtr"
      "shuymn/tap/kastty"
      "shuymn/tap/pommitlint"
      "songmu/tap/maltmill"
    ];

    casks = [
      "1password-cli"
      "appcleaner"
      "choosy"
      "codex"
      "ghostty"
      "hammerspoon"
      "jordanbaird-ice"
      "karabiner-elements"
      "linearmouse"
      "orbstack"
      "raycast"
      "ukelele"
      "visual-studio-code"
      "xdevplatform/tap/xurl"
      "zed"
    ];
  };
}
