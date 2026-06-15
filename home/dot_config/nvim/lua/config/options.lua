require("mini.basics").setup({
	options = {
		extra_ui = true
	},
	silent = true
})

vim.g.maplocalleader = " "

local opt = vim.opt

opt.autoread = true
opt.clipboard = "unnamedplus"
opt.completeopt:append("fuzzy")
opt.confirm = true
opt.inccommand = "split"
opt.relativenumber = true
opt.scrolloff = 4
opt.sidescrolloff = 8
opt.showtabline = 2
opt.termguicolors = true
opt.wildmode = "longest:full,full"

opt.diffopt:append({ "algorithm:histogram", "indent-heuristic" })
