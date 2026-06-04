{
  description = "dotfiles package profile";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-26.05-darwin";

    home-manager = {
      url = "github:nix-community/home-manager/release-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nix-darwin = {
      url = "github:LnL7/nix-darwin";
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
      localConfig =
        if localConfigPath == "" then
          import ./nix/local.default.nix
        else
          import localConfigPath;
      unfreePackageNames = [
        "1password-cli"
        "claude-code"
      ];
      system = localConfig.system;
      username = localConfig.username;
    in
    {
      darwinConfigurations.default = nix-darwin.lib.darwinSystem {
        inherit system;
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
            home-manager.users.${username} = import ./nix/home.nix;
          }
        ];
      };

      packages.${system} = {
        darwin-rebuild = nix-darwin.packages.${system}.darwin-rebuild;
      };

      apps.${system}.darwin-rebuild = {
        type = "app";
        program = "${nix-darwin.packages.${system}.darwin-rebuild}/bin/darwin-rebuild";
        meta.description = "Run nix-darwin rebuild for this dotfiles flake";
      };
    };
}
