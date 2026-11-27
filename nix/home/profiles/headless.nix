{ config, ... }:

let
  logFile = "${config.home.homeDirectory}/Library/Logs/rex-server.log";
in
{
  # Keeps a Rex server up from login so other Macs reach this one with `rex -S`.
  # `rex server install` cannot start one on macOS yet, and Rex has no Homebrew
  # cask or Nix package, so the RexServer bundle is copied in by hand from a Mac
  # that has Rex.app; a newer Rex needs a fresh copy.
  launchd.agents.rex-server = {
    enable = true;
    config = {
      ProgramArguments = [
        "${config.home.homeDirectory}/Library/Application Support/com.superlogical.rex/RexServer/Versions/Current/Rex Server.app/Contents/MacOS/rex"
        "server"
        "run"
      ];
      RunAtLoad = true;
      KeepAlive = true;
      ProcessType = "Interactive";
      StandardOutPath = logFile;
      StandardErrorPath = logFile;
    };
  };
}
