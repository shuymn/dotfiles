{
  description = "dotfiles package profile";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-26.05-darwin";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

    home-manager = {
      url = "github:nix-community/home-manager/release-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nix-darwin = {
      url = "github:nix-darwin/nix-darwin/nix-darwin-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    capsule = {
      url = "github:shuymn/capsule";
      # Keep the upstream package pin for its release binary cache.
      inputs.home-manager.follows = "home-manager";
      inputs.nix-darwin.follows = "nix-darwin";
    };
  };

  outputs =
    {
      capsule,
      home-manager,
      nix-darwin,
      nixpkgs-unstable,
      ...
    }:
    let
      # host.toml is git-ignored, so it exists only when the flake is evaluated
      # from a path: reference to the checkout (see Makefile).
      defaultConfig = builtins.fromTOML (
        builtins.readFile (if builtins.pathExists ./host.toml then ./host.toml else ./nix/host.default.toml)
      );
      unfreePackageNames = [
        "1password-cli"
        "acli"
      ];
      # Single source for the mise version used by Home Manager and CI lockfile regeneration.
      miseFor = system: nixpkgs-unstable.legacyPackages.${system}.mise;
      mkDarwinConfiguration =
        localConfig:
        nix-darwin.lib.darwinSystem {
          system = localConfig.system;
          specialArgs = {
            inherit localConfig unfreePackageNames;
          };
          modules = [
            ./nix/darwin
            home-manager.darwinModules.home-manager
            {
              nixpkgs.overlays = [
                (final: prev: {
                  # nixpkgs の pre-commit は nativeCheckInputs/preCheck で dotnet-sdk を要求する。
                  # aarch64-darwin では dotnet-vmr(.NET のソースビルド)が Hydra で失敗/中断
                  # することがあり、キャッシュ未提供の revision に lock が進むと switch 時に
                  # 1〜2 時間のローカルビルドが走る。テスト専用依存なので実行時の動作は
                  # 変わらない。doCheck = false だけでは preCheck の参照が残るため、
                  # チェック入力そのものを空にする。pytestCheckHook は依存の cfgv 経由で
                  # 環境に入り doCheck を見ずに pytestCheckPhase を登録するため、
                  # dontUsePytestCheck で明示的に無効化する。
                  pre-commit = prev.pre-commit.overridePythonAttrs (_: {
                    doCheck = false;
                    dontUsePytestCheck = true;
                    nativeCheckInputs = [ ];
                    checkInputs = [ ];
                    preCheck = "";
                  });

                  # nixpkgs の granted はソースビルドのため ad-hoc 署名のみで
                  # TeamIdentifier を持たず、macOS キーチェーンの ACL を安定して
                  # 紐付けられない。結果として credential_process 経由で
                  # `aws --profile <name> ...` を実行するたびに、ログイン
                  # キーチェーンのパスワード入力を求められる。安定した
                  # identifier を付けて再署名し、「常に許可」を効かせる。
                  # https://github.com/fwdcloudsec/granted/issues/936
                  granted = prev.granted.overrideAttrs (oldAttrs: {
                    nativeBuildInputs = (oldAttrs.nativeBuildInputs or [ ]) ++ [ final.darwin.sigtool ];
                    postFixup = (oldAttrs.postFixup or "") + ''
                      codesign --force --sign - --identifier dev.granted.cli $out/bin/granted
                    '';
                  });

                  # Use unstable mise until the 26.05 darwin pin includes the HTTP backend symlink fix.
                  mise = miseFor localConfig.system;
                })
              ];

              home-manager.useGlobalPkgs = true;
              home-manager.useUserPackages = true;
              home-manager.extraSpecialArgs = {
                inherit capsule localConfig;
              };
              home-manager.users.${localConfig.username} = import ./nix/home;
            }
          ];
        };
      defaultDarwinConfiguration = mkDarwinConfiguration defaultConfig;
      pkgs = defaultDarwinConfiguration.pkgs;
    in
    {
      darwinConfigurations.default = defaultDarwinConfiguration;

      checks.${defaultConfig.system} = import ./nix/checks.nix {
        inherit pkgs;
        inherit (pkgs) lib;
        roles = builtins.fromTOML (builtins.readFile ./nix/roles.toml);
        homeConfigurationFor =
          role:
          (mkDarwinConfiguration (defaultConfig // { inherit role; }))
          .config.home-manager.users.${defaultConfig.username};
      };

      packages.${defaultConfig.system} = {
        mise = miseFor defaultConfig.system;
        darwin-rebuild = nix-darwin.packages.${defaultConfig.system}.darwin-rebuild;
      };

      apps.${defaultConfig.system}.darwin-rebuild = {
        type = "app";
        program = "${nix-darwin.packages.${defaultConfig.system}.darwin-rebuild}/bin/darwin-rebuild";
        meta.description = "Run nix-darwin rebuild for this dotfiles flake";
      };
    };
}
