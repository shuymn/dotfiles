require("nvim-treesitter.configs").setup({
	ensure_installed = "all",
	ignore_install = { "phpdoc" },
	highlight = {
		enable = true,
		additional_vim_regex_highlighting = false,
	},
	incremental_selection = {
		enable = true,
		keymaps = {
			init_selection = "<CR>",
			scope_incremental = "<CR>",
			node_incremental = "<TAB>",
			node_decremental = "<S-TAB>",
		},
	},
	indent = { enable = false },
	textobjects = {
		select = {
			enable = true,
			disable = {},
			keymaps = {
				["af"] = "@function.outer",
				["if"] = "@function.inner",
				["ac"] = "@class.outer",
				["ic"] = "@class.inner",
				["iB"] = "@block.inner",
				["aB"] = "@block.outer",
				["ii"] = "@conditional.inner",
				["ai"] = "@conditional.outer",
				["il"] = "@loop.inner",
				["al"] = "@loop.outer",
				["ip"] = "@parameter.inner",
				["ap"] = "@parameter.outer",
			},
		},
		swap = {
			enable = true,
			swap_next = { ["'>"] = "@parameter.inner" },
			swap_previous = { ["'<"] = "@parameter.inner" },
		},
		move = {
			enable = true,
			goto_next_start = { ["]m"] = "@function.outer", ["]]"] = "@class.outer" },
			goto_next_end = { ["]M"] = "@function.outer", ["]["] = "@class.outer" },
			goto_previous_start = { ["[m"] = "@function.outer", ["[["] = "@class.outer" },
			goto_previous_end = { ["[M"] = "@function.outer", ["[]"] = "@class.outer" },
		},
	},
	rainbow = {
		enable = true,
		extended_mode = true,
		max_file_lines = 300,
	},
	matchup = { enable = true },
	context_commentstring = { enable = true },
	yati = { enable = true },
})
