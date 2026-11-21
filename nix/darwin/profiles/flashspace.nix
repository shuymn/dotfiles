# FlashSpace shows and hides apps per workspace; Hammerspoon lays out the windows
# of opted-in apps (home/dot_config/hammerspoon/init.lua).
{
  homebrew.casks = [
    "flashspace"
    "hammerspoon"
  ];

  # FlashSpace needs "Displays have separate Spaces" (takes effect after re-login).
  system.defaults.spaces.spans-displays = false;

  system.defaults.CustomUserPreferences."org.hammerspoon.Hammerspoon".MJConfigFile =
    "~/.config/hammerspoon/init.lua";
}
