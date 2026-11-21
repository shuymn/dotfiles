{ config, pkgs, ... }:

let
  lspPackages = with pkgs; [
    basedpyright
    # Build with the Go that mise provides; vscode-go asks to recompile a gopls
    # built with an older Go, and gopls cannot check newer language features.
    (gopls.override { buildGoLatestModule = buildGo127Module; })
    lua-language-server
    nixd
    ruff
    taplo
    typescript
    typescript-language-server
    vscode-langservers-extracted
    yaml-language-server
  ];
in
{
  home.packages =
    with pkgs;
    [
      _1password-cli
      awscli2
      bat
      biome
      claude-recall
      delta
      difftastic
      eza
      fd
      fzf
      ghq
      gh-stack
      gnused
      gotools
      govulncheck
      jq
      nixfmt
      pre-commit
      rustup
      semgrep
      shfmt
      sops
      sqlmap
      yamllint
      yq
      zoxide
      zsh-completions
      zsh-fast-syntax-highlighting
    ]
    ++ lspPackages;

  programs.direnv = {
    enable = true;
    enableBashIntegration = false;
    enableFishIntegration = false;
    enableNushellIntegration = false;
    enableZshIntegration = false;

    nix-direnv.enable = true;
  };

  programs.gh = {
    enable = true;

    gitCredentialHelper.enable = false;

    settings = {
      aliases.infra = ''!gh-infra "$@"'';
      aliases.stack = ''!gh-stack "$@"'';
      git_protocol = "https";
      prompt = "enabled";
      pager = "delta";
    };
  };

  # The stack cycle (scripts/stack-cycle): stack-observe, then stack-improve, run from the dotfiles checkout;
  # improve stays off until ~/.config/stack/improve.toml enables it and then runs claude, codex and gh through the
  # mise shims. stack and its extensions live in ~/.local/bin. launchd starts a calendar job missed while asleep on
  # wake and runs one instance of a label at a time. The script runs from its store copy, so a change takes effect
  # at the next switch.
  launchd.agents.stack-cycle = {
    enable = true;
    config = {
      ProgramArguments = [
        "/bin/sh"
        "${../../../scripts/stack-cycle}"
      ];
      StartCalendarInterval = [
        {
          Hour = 6;
          Minute = 0;
        }
      ];
      EnvironmentVariables.PATH = "${config.home.homeDirectory}/.local/bin:${config.home.profileDirectory}/bin:/usr/bin:/bin:/usr/sbin:/sbin:${config.home.homeDirectory}/.local/share/mise/shims";
      ProcessType = "Background";
      LowPriorityIO = true;
      StandardOutPath = "${config.home.homeDirectory}/Library/Logs/stack-cycle.log";
      StandardErrorPath = "${config.home.homeDirectory}/Library/Logs/stack-cycle.log";
    };
  };
}
