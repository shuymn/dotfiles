return {
  {
    "stevearc/conform.nvim",
    -- event = 'BufWritePre', -- uncomment for format on save
    opts = require "configs.conform",
  },

  {
    "neovim/nvim-lspconfig",
    config = function()
      require "configs.lspconfig"
    end,
  },

  {
    "nvim-treesitter/nvim-treesitter",
    opts = {
      ensure_installed = {
        "vim",
        "lua",
        "vimdoc",
        "go",
        "bash",
      },
    },
  },

  {
    "phaazon/hop.nvim",
    branch = "v2",
    lazy = false,
    config = function()
      local hop = require "hop"
      local directions = require("hop.hint").HintDirection
      hop.setup()

      vim.keymap.set("", "f", function()
        hop.hint_char1 { direction = directions.AFTER_CURSOR, current_line_only = true }
      end, { remap = true })
      vim.keymap.set("", "F", function()
        hop.hint_char1 { direction = directions.BEFORE_CURSOR, current_line_only = true }
      end, { remap = true })
    end,
  },

    {
      'mikesmithgh/kitty-scrollback.nvim',
      lazy = true,
      cmd = { 'KittyScrollbackGenerateKittens', 'KittyScrollbackCheckHealth', 'KittyScrollbackGenerateCommandLineEditing' },
      event = { 'User KittyScrollbackLaunch' },
      version = '^6.0.0', -- pin major version, include fixes and features that do not have breaking changes
      config = function()
        require('kitty-scrollback').setup({
          {
            visual_selection_highlight_mode = 'kitty',
          }
        })
      end,
    },

  {
    "nvim-telescope/telescope.nvim",
    opts = function(_, conf)
      conf.pickers = {
        current_buffer_fuzzy_find = {
          previewer = false,
        },
      }
      return conf
    end,
  },

  {
    "github/copilot.vim",
    lazy = false,
  },
}
