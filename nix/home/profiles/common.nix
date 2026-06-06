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

    plugins = with pkgs.vimPlugins; [
      vim-sleuth
      mini-nvim
      gitsigns-nvim
      fzf-lua
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
      -- Lightweight defaults for short $EDITOR sessions.
      vim.g.mapleader = " "
      vim.g.maplocalleader = " "

      local opt = vim.opt

      opt.autoread = true
      opt.breakindent = true
      opt.clipboard = "unnamedplus"
      opt.confirm = true
      opt.cursorline = true
      opt.ignorecase = true
      opt.inccommand = "split"
      opt.linebreak = true
      opt.list = true
      opt.listchars = {
        tab = "» ",
        trail = "·",
        nbsp = "␣",
      }
      opt.number = true
      opt.relativenumber = true
      opt.scrolloff = 4
      opt.sidescrolloff = 8
      opt.signcolumn = "yes"
      opt.smartcase = true
      opt.splitbelow = true
      opt.splitright = true
      opt.termguicolors = true
      opt.undofile = true
      opt.virtualedit = "block"
      opt.wildmode = "longest:full,full"
      opt.wrap = true

      opt.diffopt:append({ "algorithm:histogram", "indent-heuristic" })

      vim.keymap.set("n", "<Esc>", "<cmd>nohlsearch<CR>", { silent = true, desc = "Clear search highlight" })
      vim.keymap.set("n", "j", "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true })
      vim.keymap.set("n", "k", "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true })
      vim.keymap.set("n", "x", '"_x', { silent = true })
      vim.keymap.set("x", "x", '"_x', { silent = true })

      vim.keymap.set("n", "<leader><leader>", "<cmd>FzfLua commands<CR>", { desc = "Command palette" })
      vim.keymap.set("n", "<leader>?", "<cmd>FzfLua keymaps<CR>", { desc = "Search keymaps" })
      vim.keymap.set("n", "<leader>ff", "<cmd>FzfLua files<CR>", { desc = "Find files" })
      vim.keymap.set("n", "<leader>fg", "<cmd>FzfLua live_grep<CR>", { desc = "Live grep" })
      vim.keymap.set("n", "<leader>fb", "<cmd>FzfLua buffers<CR>", { desc = "Find buffers" })
      vim.keymap.set("n", "<leader>fh", "<cmd>FzfLua help_tags<CR>", { desc = "Find help" })

      vim.api.nvim_create_autocmd("BufReadPost", {
        callback = function()
          local mark = vim.api.nvim_buf_get_mark(0, '"')
          local line_count = vim.api.nvim_buf_line_count(0)

          if mark[1] > 0 and mark[1] <= line_count then
            pcall(vim.api.nvim_win_set_cursor, 0, mark)
          end
        end,
      })

      vim.api.nvim_create_autocmd("TextYankPost", {
        callback = function()
          vim.highlight.on_yank({ timeout = 150 })
        end,
      })

      vim.cmd.packadd("github-nvim-theme")
      vim.cmd.packadd("nvim-treesitter")

      require("github-theme").setup({})
      vim.cmd.colorscheme("github_dark")

      require("mini.ai").setup({})
      require("mini.comment").setup({})
      require("mini.pairs").setup({})
      require("mini.statusline").setup({
        use_icons = false,
      })
      require("mini.surround").setup({})
      require("gitsigns").setup({})
      require("fzf-lua").setup({})

      vim.api.nvim_create_autocmd("FileType", {
        callback = function()
          pcall(vim.treesitter.start)
        end,
      })
    '';
  };

}
