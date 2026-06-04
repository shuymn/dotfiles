{
  description = "dotfiles package profile";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-26.05-darwin";

    home-manager = {
      url = "github:nix-community/home-manager/release-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nix-darwin = {
      url = "github:nix-darwin/nix-darwin/nix-darwin-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      home-manager,
      nix-darwin,
      ...
    }:
    let
      localConfigPath = builtins.getEnv "DOTFILES_NIX_LOCAL";
      defaultConfig =
        if localConfigPath == "" then
          import ./nix/local.default.nix
        else
          import localConfigPath;
      unfreePackageNames = [
        "1password-cli"
        "claude-code"
      ];
      mkDarwinConfiguration =
        localConfig:
        nix-darwin.lib.darwinSystem {
          system = localConfig.system;
          specialArgs = {
            inherit localConfig unfreePackageNames;
          };
          modules = [
            ./nix/darwin.nix
            home-manager.darwinModules.home-manager
            {
              home-manager.useGlobalPkgs = true;
              home-manager.useUserPackages = true;
              home-manager.extraSpecialArgs = {
                inherit localConfig;
              };
              home-manager.users.${localConfig.username} = import ./nix/home.nix;
            }
          ];
        };
    in
    {
      darwinConfigurations.default = mkDarwinConfiguration defaultConfig;

      packages.${defaultConfig.system} = {
        darwin-rebuild = nix-darwin.packages.${defaultConfig.system}.darwin-rebuild;
      };

      apps.${defaultConfig.system}.darwin-rebuild = {
        type = "app";
        program = "${nix-darwin.packages.${defaultConfig.system}.darwin-rebuild}/bin/darwin-rebuild";
        meta.description = "Run nix-darwin rebuild for this dotfiles flake";
      };
    };
}
