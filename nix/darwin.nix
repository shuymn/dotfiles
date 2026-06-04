{ lib, localConfig, unfreePackageNames, ... }:

{
  system.stateVersion = 5;
  system.primaryUser = localConfig.username;

  nixpkgs.hostPlatform = localConfig.system;
  nixpkgs.config.allowUnfreePredicate = pkg: builtins.elem (lib.getName pkg) unfreePackageNames;

  nix.settings = {
    experimental-features = [
      "nix-command"
      "flakes"
    ];
    nix-path = [ "nixpkgs=flake:nixpkgs" ];
    trusted-users = [
      "root"
      localConfig.username
    ];
  };
  nix.nixPath = [ "nixpkgs=flake:nixpkgs" ];

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
      cleanup = "check";
    };

    global = {
      autoUpdate = false;
      brewfile = true;
    };

    taps = [
      "coderabbitai/tap"
      "shuymn/tap"
      "songmu/tap"
      "xdevplatform/tap"
    ];

    brews = [
      "coderabbitai/tap/git-gtr"
      "shuymn/tap/capsule"
      "shuymn/tap/kastty"
      "shuymn/tap/pommitlint"
      "songmu/tap/maltmill"
    ];

    casks = [
      "appcleaner"
      "choosy"
      "codex"
      "ghostty"
      "hammerspoon"
      "jordanbaird-ice"
      "karabiner-elements"
      "linearmouse"
      "lm-studio"
      "orbstack"
      "raycast"
      "tailscale-app"
      "ukelele"
      "visual-studio-code"
      "xdevplatform/tap/xurl"
      "zed"
    ];
  };
}
