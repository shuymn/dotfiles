{
  lib,
  localConfig,
  unfreePackageNames,
  ...
}:

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
    min-free = 20 * 1024 * 1024 * 1024;
    max-free = 80 * 1024 * 1024 * 1024;
    nix-path = [ "nixpkgs=flake:nixpkgs" ];
    trusted-users = [
      "root"
      localConfig.username
    ];
  };

  nix.optimise.automatic = true;

  nix.gc = {
    automatic = true;
    interval = {
      Hour = 3;
      Minute = 0;
    };
    options = "--delete-older-than 7d";
  };
  nix.nixPath = [ "nixpkgs=flake:nixpkgs" ];

  networking = {
    computerName = localConfig.computerName;
    hostName = localConfig.hostName;
    localHostName = localConfig.hostName;
  };

  system.defaults = {
    NSGlobalDomain = {
      ApplePressAndHoldEnabled = false;
      AppleShowAllExtensions = true;
      AppleShowScrollBars = "Always";
      AppleWindowTabbingMode = "manual";
      InitialKeyRepeat = 15;
      KeyRepeat = 2;
      NSAutomaticPeriodSubstitutionEnabled = false;
    };

    dock = {
      autohide = true;
      mru-spaces = false;
      show-recents = false;
      static-only = true;
      tilesize = 48;
      wvous-bl-corner = 1;
      wvous-br-corner = 1;
      wvous-tl-corner = 1;
      wvous-tr-corner = 1;
    };

    spaces = {
      spans-displays = true;
    };

    finder = {
      AppleShowAllFiles = true;
      FXDefaultSearchScope = "SCcf";
      FXPreferredViewStyle = "Nlsv";
      FXRemoveOldTrashItems = true;
      ShowPathbar = true;
      ShowStatusBar = true;
      _FXShowPosixPathInTitle = true;
      _FXSortFoldersFirst = true;
      _FXSortFoldersFirstOnDesktop = true;
    };

    screencapture = {
      location = "${localConfig.homeDirectory}/Pictures";
    };

    CustomUserPreferences = {
      "com.apple.desktopservices" = {
        DSDontWriteNetworkStores = true;
        DSDontWriteUSBStores = true;
      };
    };
  };

  users.users.${localConfig.username}.home = localConfig.homeDirectory;
  programs.zsh.enable = true;

  security.pam.services.sudo_local = {
    touchIdAuth = true;
    reattach = true;
  };

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
      "shuymn/tap"
    ];

    brews = [
      "shuymn/tap/capsule"
    ];
  };
}
