{ pkgs, ... }:

let
  lspPackages = with pkgs; [
    basedpyright
    gopls
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
      agent-browser
      bat
      biome
      delta
      difftastic
      eza
      fd
      fzf
      ghq
      glimpseui
      gnused
      golangci-lint
      gotools
      govulncheck
      jq
      nixfmt
      pre-commit
      rustup
      semgrep
      shellcheck
      shfmt
      sops
      sqlmap
      tmux
      yamllint
      yazi
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
      git_protocol = "ssh";
      prompt = "enabled";
      pager = "delta";
    };
  };

  programs.gh-dash = {
    enable = true;

    settings = {
      prSections = [
        {
          title = "Mine";
          filters = "is:open author:@me";
        }
        {
          title = "Needs Review";
          filters = "is:open review-requested:@me -author:@me";
        }
        {
          title = "Involved";
          filters = "is:open involves:@me -author:@me -review-requested:@me";
        }
        {
          title = "Recently Merged";
          filters = "is:merged author:@me";
          limit = 10;
        }
      ];

      issuesSections = [
        {
          title = "Assigned";
          filters = "is:open assignee:@me";
        }
        {
          title = "Created";
          filters = "is:open author:@me";
        }
        {
          title = "Involved";
          filters = "is:open involves:@me -author:@me";
        }
      ];

      defaults = {
        view = "prs";
        refetchIntervalMinutes = 10;
        prsLimit = 20;
        issuesLimit = 20;

        preview = {
          open = true;
          width = 80;
        };
      };

      pager = {
        diff = "delta --paging=never";
      };

      smartFilteringAtLaunch = true;
    };
  };
}
