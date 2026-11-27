# A Mac that runs with the lid closed and is reached only over SSH, Rex, and
# Screen Sharing. Screen Sharing and automatic login are turned on in System
# Settings, which writes the kcpassword that a defaults key alone cannot.
{ lib, localConfig, ... }:

{
  # Password logins end below, so stop before activation while no key can log in.
  system.activationScripts.preActivation.text = ''
    if [ ! -s ${lib.escapeShellArg "${localConfig.homeDirectory}/.ssh/authorized_keys"} ]; then
      echo "headless: add a key to ~/.ssh/authorized_keys before password SSH is turned off" >&2
      exit 1
    fi
  '';

  power.sleep = {
    computer = "never";
    display = 10;
    harddisk = "never";
  };

  # Closing the lid without an external display still sleeps unless sleep is
  # disabled outright; power.sleep has no option for it.
  system.activationScripts.postActivation.text = ''
    pmset -a disablesleep 1
  '';

  services.openssh = {
    enable = true;
    extraConfig = ''
      PasswordAuthentication no
      KbdInteractiveAuthentication no
    '';
  };

  # A macOS update restarts the Mac with nobody at the screen; install them by hand.
  system.defaults.SoftwareUpdate.AutomaticallyInstallMacOSUpdates = false;

}
