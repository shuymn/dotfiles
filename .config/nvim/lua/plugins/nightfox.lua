local nightfox = require("nightfox")
local compile_path = vim.fn.stdpath("cache") .. "/nightfox"

nightfox.setup({
	options = {
		compile_path = compile_path,
		styles = {
			comments = "italic",
		},
	},
})

vim.cmd([[ colorscheme nightfox ]])

if vim.fn.isdirectory(compile_path) == 0 then
	nightfox.compile()
end
