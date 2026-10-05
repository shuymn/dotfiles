# $HOME targets and activation steps Home Manager may own. chezmoi owns every
# other dotfile; checks.nix rejects anything outside these lists and any
# chezmoi target that collides with them.
{
  homeFiles = [
    ".cache/.keep"
    ".config/direnv/lib/hm-nix-direnv.sh"
    ".config/gh-dash/config.yml"
    ".config/gh/config.yml"
    ".local/share/gh/extensions"
    ".local/share/nvim/site/pack/hm"
    ".local/state/.keep"
    "Library/Fonts/.home-manager-fonts-version"
  ];

  activation = [
    "checkAppManagementPermission"
    "checkFilesChanged"
    "checkLinkTargets"
    "copyApps"
    "installPackages"
    "linkGeneration"
    "migrateGhAccounts"
    "onFilesChange"
    "setupLaunchAgents"
    "writeBoundary"
  ];
}
