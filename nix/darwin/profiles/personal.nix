{
  homebrew = {
    casks = [
      "cherry-studio"
      "discord"
      "grok-bot"
      "obsidian"
      "orcaslicer"
      "zotero"
    ];
  };

  system.defaults.NSGlobalDomain._HIHideMenuBar = false;
  system.defaults.CustomUserPreferences."com.apple.controlcenter".AutoHideMenuBarOption = 3;
}
