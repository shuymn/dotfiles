{ lib, ... }:
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
      settings = lib.importTOML ../aerospace.toml;
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
