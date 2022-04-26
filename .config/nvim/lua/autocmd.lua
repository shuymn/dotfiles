local groupname = "vimrc_vimrc"
vim.api.nvim_create_augroup(groupname, { clear = true })

vim.api.nvim_create_autocmd({ "BufEnter", "FocusGained", "InsertLeave", "WinEnter" }, {
	group = groupname,
	pattern = "*",
	callback = function()
		if vim.o.nu and vim.fn.mode() ~= "i" then
			vim.o.rnu = true
		end
	end,
	once = false,
})

vim.api.nvim_create_autocmd({ "BufLeave", "FocusLost", "InsertEnter", "WinLeave" }, {
	group = groupname,
	pattern = "*",
	callback = function()
		if vim.o.nu then
			vim.o.rnu = false
		end
	end,
	once = false,
})

vim.api.nvim_create_autocmd({ "TextYankPost" }, {
	group = groupname,
	pattern = "*",
	callback = function()
		vim.highlight.on_yank({
			higroup = (vim.fn.hlexists("HighlightedyankRegion") > 0 and "HighlightedyankRegion" or "Visual"),
			timeout = 200,
		})
	end,
	once = false,
})

vim.api.nvim_create_autocmd({ "FileType" }, {
	group = groupname,
	pattern = { "gitcommit" },
	callback = function()
		vim.cmd([[startinsert]])
	end,
	once = false,
})

vim.api.nvim_create_autocmd({ "FileType" }, {
	group = groupname,
	pattern = "*",
	callback = function()
		vim.opt_local.formatoptions:remove({ "c", "r", "o" })
	end,
	once = false,
})

vim.api.nvim_create_autocmd({ "VimResized" }, {
	group = groupname,
	pattern = "*",
	callback = function()
		require("bufresize").resize()
	end,
	once = false,
})
