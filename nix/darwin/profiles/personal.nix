{
  homebrew = {
    brews = [
      "cliproxyapi"
    ];
    casks = [
      "cherry-studio"
      "discord"
      "grok-bot"
      "nani"
      "obsidian"
      "orcaslicer"
      "t3-code"
      "zotero"
    ];
  };

  system.defaults.NSGlobalDomain._HIHideMenuBar = false;
  system.defaults.CustomUserPreferences."com.apple.controlcenter".AutoHideMenuBarOption = 3;
}
