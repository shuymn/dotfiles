require("config-local").setup({
	config_files = { ".nvim/local.lua", ".nvim/local.vim" },
	hashfile = vim.fn.stdpath("data") .. "/config-local",
	autocommands_create = true,
	commands_create = true,
	silent = false,
})
