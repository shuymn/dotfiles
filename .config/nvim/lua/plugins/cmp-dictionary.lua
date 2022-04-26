local file = "/usr/share/dict/words"
local dic = {}
if vim.fn.filereadable(file) ~= 0 then
	dic = file
end

require("cmp_dictionary").setup({
	dic = { ["*"] = dic },
	exact = 2,
	async = false,
	capacity = 5,
	debug = false,
})
