vim.cmd.packadd("catppuccin-nvim")
vim.cmd.packadd("nvim-treesitter")

require("catppuccin").setup({
	flavour = "mocha",
})
vim.cmd.colorscheme("catppuccin")

require("mini.icons").setup({})
require("mini.ai").setup({})
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "json", "jsonc" },
	callback = function()
		vim.b.miniai_config = {
			n_lines = 10000,
		}
	end,
})
require("mini.comment").setup({})
require("mini.bracketed").setup({})
require("mini.completion").setup({
	lsp_completion = {
		process_items = require("mini.fuzzy").process_lsp_items,
	},
})
require("mini.visits").setup({})
require("mini.files").setup({})
require("mini.fuzzy").setup({})
require("mini.misc").setup_restore_cursor()
require("mini.pairs").setup({})
require("mini.pick").setup({
	options = {
		use_cache = true,
	},
	window = {
		prompt_prefix = "Pick: ",
	},
})
require("mini.extra").setup({})

local miniclue = require("mini.clue")
miniclue.setup({
	window = {
		config = function(buf_id)
			local line_count = vim.api.nvim_buf_line_count(buf_id)
			return {
				anchor = "SW",
				height = math.min(line_count, 12, math.max(1, vim.o.lines - 4)),
				width = math.min(60, math.max(30, vim.o.columns - 4)),
				row = "auto",
				col = "auto",
			}
		end,
		delay = 500,
	},
	triggers = {
		{ mode = { "n", "x" }, keys = "<Leader>" },
		{ mode = "n",          keys = "[" },
		{ mode = "n",          keys = "]" },
		{ mode = "i",          keys = "<C-x>" },
		{ mode = { "n", "x" }, keys = "g" },
		{ mode = { "n", "x" }, keys = "'" },
		{ mode = { "n", "x" }, keys = "`" },
		{ mode = { "n", "x" }, keys = '"' },
		{ mode = { "i", "c" }, keys = "<C-r>" },
		{ mode = "n",          keys = "<C-w>" },
		{ mode = { "n", "x" }, keys = "z" },
	},
	clues = {
		{ mode = "n", keys = "<Leader>l", desc = "+LSP" },
		{ mode = "n", keys = "<Leader>b", desc = "+Buffer" },
		{ mode = "n", keys = "K",         desc = "Hover docs" },
		{ mode = "n", keys = "gd",        desc = "Go to definition" },
		{ mode = "n", keys = "gr",        desc = "Go to references" },
		{ mode = "n", keys = "gi",        desc = "Go to implementation" },
		{ mode = "n", keys = "gt",        desc = "Go to type definition" },
		miniclue.gen_clues.square_brackets(),
		miniclue.gen_clues.builtin_completion(),
		miniclue.gen_clues.g(),
		miniclue.gen_clues.marks(),
		miniclue.gen_clues.registers(),
		miniclue.gen_clues.windows(),
		miniclue.gen_clues.z(),
	},
})

require("mini.starter").setup({})
require("mini.statusline").setup({})
require("mini.tabline").setup({})
require("mini.bufremove").setup({})
require("mini.surround").setup({})
require("mini.diff").setup({})
local jump2d = require("mini.jump2d")
jump2d.setup({
	mappings = {
		start_jumping = "",
	},
})
vim.api.nvim_set_hl(0, "MiniJump2dSpot", { bg = "#f38ba8", fg = "#11111b", bold = true })
vim.api.nvim_set_hl(0, "MiniJump2dSpotUnique", { bg = "#f38ba8", fg = "#11111b", bold = true })
vim.api.nvim_set_hl(0, "MiniJump2dSpotAhead", { fg = "#f38ba8", bold = true })

local jump2d_single_character = function(direction_opts)
	local char = vim.fn.getcharstr()
	if char == "" then
		return
	end

	jump2d.start(vim.tbl_deep_extend("force", {
		spotter = jump2d.gen_spotter.pattern(vim.pesc(char)),
		allowed_lines = {
			blank = false,
			fold = false,
		},
		allowed_windows = {
			not_current = false,
		},
	}, direction_opts))
end

local function jump2d_forward()
	jump2d_single_character({
		allowed_lines = {
			cursor_before = false,
		},
	})
end

local function jump2d_backward()
	jump2d_single_character({
		allowed_lines = {
			cursor_after = false,
		},
	})
end

vim.keymap.set({ "n", "x", "o" }, "f", jump2d_forward, { desc = "Jump2d forward to character" })
vim.keymap.set({ "n", "x", "o" }, "F", jump2d_backward, { desc = "Jump2d backward to character" })
