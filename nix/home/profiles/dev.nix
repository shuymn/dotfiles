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

  # The kaizen cycle (docs/kaizen.md §6): a stateless run over the last 7 days
  # whose daily stages call no model; the weekly stage, off until
  # ~/.claude/kaizen/improve-enabled exists, runs claude and codex through the
  # mise shims. launchd starts a calendar job missed while asleep on wake and
  # runs one instance of a label at a time. The scripts run from their store
  # copy, so a change takes effect at the next switch.
  launchd.agents.kaizen-cycle = {
    enable = true;
    config = {
      ProgramArguments = [
        "${pkgs.python3}/bin/python3"
        "${../../../scripts/kaizen}/cycle.py"
      ];
      StartCalendarInterval = [
        {
          Hour = 6;
          Minute = 0;
        }
      ];
      EnvironmentVariables.PATH = "${config.home.profileDirectory}/bin:/usr/bin:/bin:/usr/sbin:/sbin:${config.home.homeDirectory}/.local/share/mise/shims";
      ProcessType = "Background";
      LowPriorityIO = true;
      StandardOutPath = "${config.home.homeDirectory}/Library/Logs/kaizen-cycle.log";
      StandardErrorPath = "${config.home.homeDirectory}/Library/Logs/kaizen-cycle.log";
    };
  };
}
