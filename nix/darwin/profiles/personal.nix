{
  homebrew = {
    brews = [
      "cliproxyapi"
    ];
    casks = [
      "cherry-studio"
      "discord"
      "grok-bot"
      "obsidian"
      "orcaslicer"
      "pen"
      "plamo-translate"
      "t3-code"
      "zotero"
    ];
  };

  system.defaults.NSGlobalDomain._HIHideMenuBar = false;
  system.defaults.CustomUserPreferences."com.apple.controlcenter".AutoHideMenuBarOption = 3;
}
