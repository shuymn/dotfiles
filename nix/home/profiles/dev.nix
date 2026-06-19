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
      direnv
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
      nix-direnv
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

  programs.gh = {
    enable = true;

    gitCredentialHelper.enable = false;

    settings = {
      git_protocol = "ssh";
      prompt = "enabled";
      pager = "hunk pager";
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
        diff = "hunk pager";
      };

      smartFilteringAtLaunch = true;
    };
  };
}
