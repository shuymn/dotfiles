{ pkgs, ... }:

{
  home.packages = with pkgs; [
    age
    atuin
    bash
    bat
    chezmoi
    curl
    delta
    direnv
    eza
    fd
    fzf
    gh
    git
    gnused
    jq
    mise
    ripgrep
    tmux
    yq
    zoxide
    zsh-completions
    zsh-fast-syntax-highlighting
  ];

  home.sessionVariables = {
    CVSEDITOR = "nvim";
    GIT_EDITOR = "nvim";
    SVN_EDITOR = "nvim";
  };

  programs.neovim = {
    enable = true;
    defaultEditor = true;
    vimAlias = true;

    plugins = with pkgs.vimPlugins; [
      {
        plugin = github-nvim-theme;
        optional = true;
      }
      {
        plugin = nvim-treesitter.withPlugins (p: [
          p.bash
          p.css
          p.diff
          p.dockerfile
          p.git_config
          p.git_rebase
          p.gitattributes
          p.gitcommit
          p.gitignore
          p.go
          p.html
          p.javascript
          p.json
          p.lua
          p.markdown
          p.markdown_inline
          p.nix
          p.python
          p.rust
          p.sql
          p.toml
          p.tsx
          p.typescript
          p.vim
          p.vimdoc
          p.yaml
          p.zsh
        ]);
        optional = true;
      }
    ];

    initLua = ''
      vim.cmd.packadd("github-nvim-theme")
      vim.cmd.packadd("nvim-treesitter")

      require("github-theme").setup({})
      vim.cmd.colorscheme("github_dark")

      vim.api.nvim_create_autocmd("FileType", {
        callback = function()
          pcall(vim.treesitter.start)
        end,
      })
    '';
  };

}
