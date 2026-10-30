{ config, pkgs, ... }:

{
  # The service starts the VM at login. isActive makes colima select its docker
  # context on start; ~/.docker/config.json stays unmanaged because
  # programs.docker-cli is not enabled.
  services.colima = {
    enable = true;
    colimaHomeDir = "${config.xdg.configHome}/colima";
    profiles.default = {
      isService = true;
      isActive = true;
      # launchd does not create the default ~/.local/state/colima directory.
      logFile = "${config.home.homeDirectory}/Library/Logs/colima.log";
      settings = {
        cpu = 8;
        disk = 100;
        memory = 24;
        arch = "aarch64";
        runtime = "docker";
        modelRunner = "docker";
        hostname = "colima";
        kubernetes = {
          enabled = false;
          version = "v1.35.0+k3s1";
          k3sArgs = [ "--disable=traefik" ];
          port = 0;
        };
        autoActivate = true;
        network = {
          address = false;
          mode = "shared";
          interface = "en0";
          preferredRoute = false;
          dns = null;
          dnsHosts = { };
          hostAddresses = false;
          gatewayAddress = "192.168.5.2";
        };
        forwardAgent = false;
        docker.log-driver = "local";
        vmType = "vz";
        portForwarder = "ssh";
        rosetta = true;
        binfmt = true;
        nestedVirtualization = false;
        mountType = "virtiofs";
        mountInotify = true;
        cpuType = "";
        provision = null;
        sshConfig = true;
        sshPort = 0;
        # Listing mounts replaces colima's default home-only share. /private/tmp
        # lets bind mounts from temp directories reach containers.
        mounts = [
          {
            location = config.home.homeDirectory;
            writable = true;
          }
          {
            location = "/private/tmp";
            writable = true;
          }
        ];
        diskImage = "";
        rootDisk = 20;
        env = { };
      };
    };
  };

  home.packages = with pkgs; [
    acli
    circleci-cli
    docker
    docker-buildx
    docker-compose
    google-cloud-sdk
    grpcurl
    phpactor
    watch
  ];
}
