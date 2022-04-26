require("indent_blankline").setup({
	show_current_context = true,
	buftype_exclude = { "terminal" },
	filetype_exclude = {
		"help",
		"neo-tree",
		"packer",
		"log",
		"lspsagafinder",
		"lspinfo",
		"toggleterm",
		"alpha",
	},
})

vim.api.nvim_clear_autocmds({ event = { "TextChanged", "TextChangedI" }, group = "IndentBlanklineAutogroup" })
