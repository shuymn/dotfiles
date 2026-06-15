{ pkgs, ... }:

{
  home.packages = with pkgs; [
    age
    atuin
    bash
    chezmoi
    curl
    git
    mise
    ripgrep
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
    sideloadInitLua = true;

    plugins = with pkgs.vimPlugins; [
      vim-sleuth
      mini-nvim
      {
        plugin = catppuccin-nvim;
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

  };

}
