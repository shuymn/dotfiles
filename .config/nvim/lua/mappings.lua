---------------------------------------------------------------------------------------------------+
-- Commands \ Modes | Normal | Insert | Command | Visual | Select | Operator | Terminal | Lang-Arg |
-- ================================================================================================+
-- map  / noremap   |    @   |   -    |    -    |   @    |   @    |    @     |    -     |    -     |
-- nmap / nnoremap  |    @   |   -    |    -    |   -    |   -    |    -     |    -     |    -     |
-- map! / noremap!  |    -   |   @    |    @    |   -    |   -    |    -     |    -     |    -     |
-- imap / inoremap  |    -   |   @    |    -    |   -    |   -    |    -     |    -     |    -     |
-- cmap / cnoremap  |    -   |   -    |    @    |   -    |   -    |    -     |    -     |    -     |
-- vmap / vnoremap  |    -   |   -    |    -    |   @    |   @    |    -     |    -     |    -     |
-- xmap / xnoremap  |    -   |   -    |    -    |   @    |   -    |    -     |    -     |    -     |
-- smap / snoremap  |    -   |   -    |    -    |   -    |   @    |    -     |    -     |    -     |
-- omap / onoremap  |    -   |   -    |    -    |   -    |   -    |    @     |    -     |    -     |
-- tmap / tnoremap  |    -   |   -    |    -    |   -    |   -    |    -     |    @     |    -     |
-- lmap / lnoremap  |    -   |   @    |    @    |   -    |   -    |    -     |    -     |    @     |
---------------------------------------------------------------------------------------------------+

local is_legendary_available, legendary = pcall(require, "legendary")
local keymaps = {}

-- Whether or not to check individually
local devopts = {
	check = false,
	count = 0,
	limit = 1,
}

local function set_keymaps(...)
	if is_legendary_available then
		vim.tbl_map(function(keymap)
			if devopts.check then
				if devopts.count < devopts.limit then
					legendary.bind_keymap(keymap)
				end
				devopts.count = devopts.count + 1
			else
				table.insert(keymaps, keymap)
			end
		end, { ... })
	end
end

-- <Leader>
set_keymaps({
	"<Leader><CR>",
	"<Cmd>WhichKey \\ <CR>",
	mode = { "n" },
	opts = { noremap = true },
	description = "WhichKey <Leader>",
})

-- <LocalLeader>
set_keymaps({
	"<LocalLeader><CR>",
	"<Cmd>WhichKey <LocalLeader><CR>",
	mode = { "n" },
	opts = { noremap = true },
	description = "WhichKey <LocalLeader>",
})

-- [SubLeader]
vim.keymap.set({ "n", "x" }, "[SubLeader]", "<Nop>", { noremap = true, silent = true })
vim.keymap.set({ "n", "x" }, ",", "<Nop>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", ",", "[SubLeader]", {})
vim.api.nvim_set_keymap("x", ",", "[SubLeader]", {})

set_keymaps({
	"[SubLeader]<CR>",
	"<Cmd>WhichKey [SubLeader]<CR>",
	mode = { "n" },
	opts = { noremap = true },
	description = "WhichKey [SubLeader]",
})

-- [lsp]
vim.keymap.set("n", "[lsp]", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", ";", "<Nop>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", ";", "[lsp]", {})

set_keymaps({
	"[lsp]<CR>",
	"<Cmd>WhichKey [lsp]<CR>",
	mode = { "n" },
	opts = { noremap = true },
	description = "WhichKey [lsp]",
})

-- [ts]
vim.keymap.set("n", "[ts]", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "'", "<Nop>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "'", "[ts]", {})

set_keymaps({
	"[ts]<CR>",
	"<Cmd>WhichKey [ts]<CR>",
	mode = { "n" },
	opts = { noremap = true },
	description = "WhichKey [ts]",
})

-- [make]
vim.keymap.set("n", "[make]", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "m", "<Nop>", { noremap = true, silent = true })

set_keymaps({
	"[make]<CR>",
	"<Cmd>WhichKey [make]<CR>",
	mode = { "n" },
	opts = { noremap = true },
	description = "WhichKey [make]",
})

-- [fuzzy-finder]
vim.keymap.set("n", "z", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "Z", "<Nop>", { noremap = true, silent = true })

set_keymaps({
	"[fuzzy-finder]<CR>",
	"<Cmd>WhichKey [fuzzy-finder]<CR>",
	mode = { "n" },
	opts = { noremap = true },
	description = "WhichKey [fuzzy-finder]",
})

-- [git]
vim.keymap.set("n", "[git]", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "G", "<Nop>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "G", "[git]", {})

set_keymaps({
	"[git]<CR>",
	"<Cmd>WhichKey [git]<CR>",
	mode = { "n" },
	opts = { noremap = true },
	description = "WhichKey [git]",
})

-- Comment.nvim
set_keymaps({
	"<C-_>",
	{
		n = "<Cmd>lua require('Comment.api').toggle_current_linewise()<CR>",
		i = "<Esc>:<C-u>lua require('Comment.api').toggle_current_linewise()<CR>\"_cc",
		v = "gc",
	},
	description = "Toggle comment",
})

-- aerial
set_keymaps({
	"gt",
	"<Cmd>:AerialToggle<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Toggle code outline",
})

-- bufferline
set_keymaps({
	"<Leader>b",
	"<Cmd>BufferLinePick<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Show selection of a buffer in view",
})

vim.keymap.set("n", "H", "<Cmd>BufferLineCyclePrev<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "L", "<Cmd>BufferLineCycleNext<CR>", { noremap = true, silent = true })

vim.keymap.set("n", "<Leader>1", "<Cmd>BufferLineGoToBuffer 1<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "<Leader>2", "<Cmd>BufferLineGoToBuffer 2<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "<Leader>3", "<Cmd>BufferLineGoToBuffer 3<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "<Leader>4", "<Cmd>BufferLineGoToBuffer 4<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "<Leader>5", "<Cmd>BufferLineGoToBuffer 5<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "<Leader>6", "<Cmd>BufferLineGoToBuffer 6<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "<Leader>7", "<Cmd>BufferLineGoToBuffer 7<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "<Leader>8", "<Cmd>BufferLineGoToBuffer 8<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "<Leader>9", "<Cmd>BufferLineGoToBuffer 9<CR>", { noremap = true, silent = true })

-- bufresize
set_keymaps({
	"<C-w>>",
	"<C-w>><Cmd>lua require('bufresize').register()<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Increase current window width",
}, {
	"<C-w><",
	"<C-w><<Cmd>lua require('bufresize').register()<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Decrease current window width",
}, {
	"<C-w>+",
	"<C-w>+<Cmd>lua require('bufresize').register()<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Increase current window height",
}, {
	"<C-w>_",
	"<C-w>-<Cmd>lua require('bufresize').register()<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Decrease current window height",
}, {
	"<C-w>=",
	"<C-w>=<Cmd>lua require('bufresize').register()<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Make all windows equally high and wide",
}, {
	"<C-w>-",
	"<C-w>_<Cmd>lua require('bufresize').register()<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Set current window height to highest possible",
})

-- tree-sitter
vim.keymap.set("n", "M", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "?", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "<C-s>", "<Nop>", { noremap = true, silent = true })

-- sandwich & <spector>
vim.keymap.set({ "n", "x" }, "s", "<Nop>", { noremap = true, silent = true })
vim.keymap.set({ "n", "x" }, "S", "<Nop>", { noremap = true, silent = true })

-- switch buffer
vim.keymap.set("n", "H", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "L", "<Nop>", { noremap = true, silent = true })

-- columnmove
vim.keymap.set("n", "J", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "K", "<Nop>", { noremap = true, silent = true })

-- lightspeed
vim.keymap.set("n", "t", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "T", "<Nop>", { noremap = true, silent = true })

-- multicursor, use RR
vim.keymap.set("n", "R", "<Nop>", { noremap = true, silent = true })

-- close
vim.keymap.set("n", "X", "<Nop>", { noremap = true, silent = true })

-- operator-replace
vim.keymap.set("n", "U", "<Nop>", { noremap = true, silent = true })

-- use 0, toggle statsuline
vim.keymap.set("n", "!", "<Nop>", { noremap = true, silent = true })

-- barbar
vim.keymap.set("n", "@", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "#", "<Nop>", { noremap = true, silent = true })

-- g; g,
vim.keymap.set("n", "^", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "&", "<Nop>", { noremap = true, silent = true })

-- <C-x>
vim.keymap.set("n", "_", "<Nop>", { noremap = true, silent = true })

-- milfeulle
vim.keymap.set("n", "<C-a>", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "<C-g>", "<Nop>", { noremap = true, silent = true })

-- buffer close
vim.keymap.set("n", "<C-x>", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "[SubLeader]bd", "<Cmd>bdelete<CR>", { noremap = true, silent = true })
set_keymaps({
	"<C-x>",
	"<Cmd>lua require('bufdelete').bufdelete(0, true)<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Delete current buffer",
})

-- switch window
vim.keymap.set("n", "<C-h>", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "<C-j>", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "<C-k>", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "<C-l>", "<Nop>", { noremap = true, silent = true })

set_keymaps({
	"<C-j>",
	"<C-w>j",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Move to the window below",
}, {
	"<C-k>",
	"<C-w>k",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Move to the upper window",
}, {
	"<C-l>",
	"<C-w>l",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Move to the right window",
}, {
	"<C-h>",
	"<C-w>h",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Move to the left window",
})

-- toggleterm
vim.keymap.set("n", "<C-z>", "<Nop>", { noremap = true, silent = true })

local toggle_term = function(direction)
	local command = "ToggleTerm"
	if direction == "h" then
		command = command .. " direction=horizontal"
	elseif direction == "v" then
		command = command .. " direction=vertical"
	end

	local bufresize = require("bufresize")
	if vim.bo.filetype == "toggleterm" then
		bufresize.block_register()
		vim.api.nvim_command(command)
		bufresize.resize_close()
	else
		bufresize.block_register()
		vim.api.nvim_command(command)
		bufresize.resize_open()
		vim.cmd([[ execute "normal! i" ]])
	end
end

set_keymaps({
	"<C-z>",
	function()
		toggle_term()
	end,
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Toggle terminal",
}, {
	"g<C-z>v",
	function()
		toggle_term("v")
	end,
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Toggle terminal vertically",
}, {
	"g<C-z>s",
	function()
		toggle_term("h")
	end,
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Toggle terminal horizontally",
})

-- vim-operator-convert-case
vim.keymap.set("n", "~", "<Nop>", { noremap = true, silent = true })

-- not use
vim.keymap.set("n", "Q", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "C", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "D", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "Y", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "=", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "<C-q>", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "qq", function()
	return vim.fn.reg_recording() == "" and "qq" or "q"
end, { noremap = true, expr = true })
vim.keymap.set("n", "q", "<Nop>", { noremap = true, silent = true })

vim.keymap.set("n", "gh", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gj", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gk", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gl", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gn", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gm", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "go", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gq", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gr", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gs", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gw", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "g^", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "g?", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gQ", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gR", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "gT", "<Nop>", { noremap = true, silent = true })

---- remap
vim.keymap.set("n", "gK", "K", { noremap = true, silent = true })
vim.keymap.set("n", "G@", "@", { noremap = true, silent = true })
vim.keymap.set("n", "g=", "=", { noremap = true, silent = true })
vim.keymap.set("n", "g?", "?", { noremap = true, silent = true })
vim.keymap.set("n", "RR", "R", { noremap = true, silent = true })
vim.keymap.set("n", "CC", '"_C', { noremap = true, silent = true })
vim.keymap.set("n", "YY", "y$", { noremap = true, silent = true })

set_keymaps({
	"DD",
	"D",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Delete the characters under the cursor until the end of the line",
}, {
	"gzz",
	"zz",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Redraw, line at center of window",
}, {
	"gg",
	description = "Goto first line",
}, {
	"GG",
	"G",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Goto last line",
}, {
	"gJ",
	"J",
	mode = { "n", "x" },
	opts = { noremap = true, silent = true },
	description = "Join lines",
}, {
	"g~",
	"~",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Change the case of current character",
}, {
	"q",
	"<Cmd>close<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Close the current window",
}, {
	"X",
	"<Cmd>tabclose<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Close current tab page",
})

-- move cursor
vim.keymap.set({ "n", "x" }, "j", function()
	return vim.v.count > 0 and "j" or "gj"
end, { noremap = true, expr = true })
vim.keymap.set({ "n", "x" }, "k", function()
	return vim.v.count > 0 and "k" or "gk"
end, { noremap = true, expr = true })

set_keymaps({
	"<C-w><C-w>",
	function()
		if vim.api.nvim_win_get_config(vim.fn.win_getid()).relative ~= "" then
			vim.cmd([[ wincmd p ]])
			return
		end
		for _, winnr in ipairs(vim.fn.range(1, vim.fn.winnr("$"))) do
			local winid = vim.fn.win_getid(winnr)
			local conf = vim.api.nvim_win_get_config(winid)
			if conf.focusable and conf.relative ~= "" then
				vim.fn.win_gotoid(winid)
				return
			end
		end
	end,
	mode = { "n" },
	opts = { noremap = true, silent = false },
	description = "Focus floating window",
})

-- jump cursor
-- Automatically indent with i and A made by ycino
vim.keymap.set("n", "i", function()
	return vim.fn.len(vim.fn.getline(".")) ~= 0 and "i" or '"_cc'
end, { noremap = true, expr = true, silent = true })
vim.keymap.set("n", "A", function()
	return vim.fn.len(vim.fn.getline(".")) ~= 0 and "A" or '"_cc'
end, { noremap = true, expr = true, silent = true })

-- toggle 0, ^ made by ycino
set_keymaps({
	"<Leader>h",
	function()
		return string.match(vim.fn.getline("."):sub(0, vim.fn.col(".") - 1), "^%s+$") and "0" or "^"
	end,
	mode = { "n" },
	opts = { noremap = true, expr = true, silent = true },
	description = "To the first of the line",
}, {
	"<Leader>l",
	function()
		return string.match(vim.fn.getline("."):sub(0, vim.fn.col(".")), "^%s+$") and "$" or "g_"
	end,
	mode = { "n" },
	opts = { noremap = true, expr = true, silent = true },
	description = "To the end of the line",
})

-- undo behavior
vim.keymap.set("i", "<BS>", "<C-g>u<BS>", { noremap = true, silent = false })
vim.keymap.set("i", "<CR>", "<C-g>u<CR>", { noremap = true, silent = false })
vim.keymap.set("i", "<DEL>", "<C-g>u<DEL>", { noremap = true, silent = false })
vim.keymap.set("i", "<C-w>", "<C-g>u<C-w>", { noremap = true, silent = false })

-- Emacs style
vim.keymap.set("c", "<C-a>", "<Home>", { noremap = true, silent = false })
if not vim.g.vscode then
	vim.keymap.set("c", "<C-e>", "<End>", { noremap = true, silent = false })
end
vim.keymap.set("c", "<C-f>", "<right>", { noremap = true, silent = false })
vim.keymap.set("c", "<C-b>", "<left>", { noremap = true, silent = false })
vim.keymap.set("c", "<C-d>", "<DEL>", { noremap = true, silent = false })
vim.keymap.set("c", "<C-s>", "<BS>", { noremap = true, silent = false })

vim.keymap.set("i", "<C-a>", "<Esc>I", { noremap = true, silent = false })
vim.keymap.set("i", "<C-e>", "<Esc>A", { noremap = true, silent = false })

vim.keymap.set("i", "<C-h>", "<left>", { noremap = true, silent = false })
vim.keymap.set("i", "<C-l>", "<right>", { noremap = true, silent = false })
vim.keymap.set("i", "<C-k>", "<up>", { noremap = true, silent = false })
vim.keymap.set("i", "<C-j>", "<down>", { noremap = true, silent = false })

-- remap H M L
set_keymaps({
	"gH",
	"H",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "To line from top of window",
}, {
	"gM",
	"M",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "To middle line of window",
}, {
	"gL",
	"L",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "To line from bottom of window",
})

-- function key
vim.keymap.set({ "i", "c", "t" }, "<F1>", "<Esc><F1>", { noremap = true, silent = true })
vim.keymap.set({ "i", "c", "t" }, "<F2>", "<Esc><F2>", { noremap = true, silent = true })
vim.keymap.set({ "i", "c", "t" }, "<F3>", "<Esc><F3>", { noremap = true, silent = true })
vim.keymap.set({ "i", "c", "t" }, "<F4>", "<Esc><F4>", { noremap = true, silent = true })
vim.keymap.set({ "i", "c", "t" }, "<F5>", "<Esc><F5>", { noremap = true, silent = true })
vim.keymap.set({ "i", "c", "t" }, "<F6>", "<Esc><F6>", { noremap = true, silent = true })
vim.keymap.set({ "i", "c", "t" }, "<F7>", "<Esc><F7>", { noremap = true, silent = true })
vim.keymap.set({ "i", "c", "t" }, "<F8>", "<Esc><F8>", { noremap = true, silent = true })
vim.keymap.set({ "i", "c", "t" }, "<F9>", "<Esc><F9>", { noremap = true, silent = true })
vim.keymap.set({ "i", "c", "t" }, "<F10>", "<Esc><F10>", { noremap = true, silent = true })
vim.keymap.set({ "i", "c", "t" }, "<F11>", "<Esc><F11>", { noremap = true, silent = true })
vim.keymap.set({ "i", "c", "t" }, "<F12>", "<Esc><F12>", { noremap = true, silent = true })

-- yank
vim.keymap.set("n", "d<Space>", "diw", { noremap = true, silent = true })
vim.keymap.set("n", "c<Space>", "ciw", { noremap = true, silent = true })
vim.keymap.set("n", "y<Space>", "yiw", { noremap = true, silent = true })
vim.keymap.set("n", "gy", "y`>", { noremap = true, silent = true })
vim.keymap.set({ "n", "x" }, "<LocalLeader>y", '"+y', { noremap = true, silent = true })
vim.keymap.set({ "n", "x" }, "<LocalLeader>d", '"+d', { noremap = true, silent = true })

-- lambdalisue's yank for slack
vim.keymap.set({ "x" }, "[SubLeader]y", function()
	vim.cmd([[ normal! y ]])
	local content = vim.fn.getreg(vim.v.register, 1, true)
	local spaces = {}
	for _, v in ipairs(content) do
		table.insert(spaces, string.match(v, "%s*"):len())
	end
	table.sort(spaces)
	local leading = spaces[1]
	local content_new = {}
	for _, v in ipairs(content) do
		table.insert(content_new, string.sub(v, leading + 1))
	end
	vim.fn.setreg(vim.v.register, content_new, vim.fn.getregtype(vim.v.register))
end, { noremap = true, silent = true })

-- paste
vim.keymap.set({ "n", "x" }, "p", "]p", { noremap = true, silent = true })
vim.keymap.set({ "n", "x" }, "gp", "p", { noremap = true, silent = true })
vim.keymap.set({ "n", "x" }, "gP", "P", { noremap = true, silent = true })
vim.keymap.set({ "n", "x" }, "<LocalLeader>p", '"+p', { noremap = true, silent = true })
vim.keymap.set({ "n", "x" }, "<LocalLeader>P", '"+P', { noremap = true, silent = true })

-- x,dはレジスタに登録しない
vim.keymap.set({ "n", "x" }, "x", '"_x', { noremap = true, silent = true })
vim.keymap.set("n", "[SubLeader]d", '"_d', { noremap = true, silent = true })
vim.keymap.set("n", "[SubLeader]D", '"_D', { noremap = true, silent = true })

-- インクリメント設定
set_keymaps({
	"+",
	"<C-a>",
	mode = { "n", "x" },
	opts = { noremap = true, silent = true },
	description = "Increment",
}, {
	"_",
	"<C-x>",
	mode = { "n", "x" },
	opts = { noremap = true, silent = true },
	description = "Decrement",
})

-- move changes
set_keymaps({
	"^",
	"g;zz",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Back to the previous position in the change list",
}, {
	"&",
	"g,zz",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Forward to the next position in the change list",
})
vim.keymap.set("n", "[;", "g;zz", { noremap = true, silent = true })
vim.keymap.set("n", "];", "g,zz", { noremap = true, silent = true })

-- clear highlighting
set_keymaps({
	"<F5>",
	":<C-u>nohlsearch<C-r>=has('diff')?'<Bar>diffupdate':''<CR><CR><C-l>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Clear the highlighting",
})
vim.keymap.set("n", "<Esc>", "<Cmd>nohlsearch<CR><C-L><Esc>", { noremap = true, silent = true })

-- move buffer
local function is_normal_buffer()
	if vim.o.ft == "qf" or vim.o.ft == "neo-tree" or vim.o.ft == "diff" then
		return false
	end
	if vim.fn.empty(vim.o.buftype) or vim.o.buftype == "terminal" then
		return true
	end
	return true
end

vim.keymap.set("n", "H", function()
	if is_normal_buffer() then
		vim.cmd([[execute "bprev"]])
	end
end, { noremap = true, silent = true })
vim.keymap.set("n", "L", function()
	if is_normal_buffer() then
		vim.cmd([[execute "bnext"]])
	end
end, { noremap = true, silent = true })

set_keymaps({
	"[q",
	"<Cmd>cprev<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Display the previous error in the list that includes a file name",
}, {
	"]q",
	"<Cmd>cnext<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Display the next error in the list that includes a file name",
}, {
	"[Q",
	"<Cmd>cfirst<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Display the first error",
}, {
	"]Q",
	"<Cmd>clast<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Display the last error",
}, {
	"[b",
	"<Cmd>bprev<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Go to previous buffer in buffer list",
}, {
	"]b",
	"<Cmd>bnext<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Go to next buffer in buffer list",
}, {
	"[B",
	"<Cmd>bfirst<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Go to first buffer in buffer list",
}, {
	"]B",
	"<Cmd>blast<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Go to last buffer in buffer list",
}, {
	"[t",
	"<Cmd>tabprev<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Go to previous tab page",
}, {
	"]t",
	"<Cmd>tabnext<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Go to the next tab page",
}, {
	"[T",
	"<Cmd>tabfirst<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Go to the first tab page",
}, {
	"]T",
	"<Cmd>tablast<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Go to the last tab page",
})

vim.keymap.set("n", "[l", "<Cmd>lprev<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "]l", "<Cmd>lnext<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "[L", "<Cmd>lfirst<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "]L", "<Cmd>llast<CR>", { noremap = true, silent = true })

-- switch quickfix/location list
set_keymaps({
	"[SubLeader]q",
	"<Cmd>copen<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Open a window to show the current list of errors",
}, {
	"[SubLeader]l",
	"<Cmd>lopen<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Open a window to show the location list for the current window",
})

-- For search
vim.keymap.set("n", "g/", "/\\v", { noremap = true, silent = false })
vim.keymap.set("n", "*", "g*N", { noremap = true, silent = true })
vim.keymap.set("x", "*", 'y/<C-R>"<CR>N', { noremap = true, silent = true })

-- noremap # g#n
vim.keymap.set({ "n", "x" }, "g*", "*N", { noremap = true, silent = true })
vim.keymap.set({ "n", "x" }, "g#", "#n", { noremap = true, silent = true })
vim.keymap.set("x", "/", "<ESC>/\\%V", { noremap = true, silent = false })
vim.keymap.set("x", "?", "<ESC>?\\%V", { noremap = true, silent = false })

-- For replace
vim.keymap.set("n", "gr", "gd[{V%::s/<C-R>///gc<left><left><left>", { noremap = true, silent = false })
vim.keymap.set("n", "gR", "gD:%s/<C-R>///gc<left><left><left>", { noremap = true, silent = false })
vim.keymap.set("n", "[SubLeader]s", ":%s/\\<<C-r><C-w>\\>/", { noremap = true, silent = false })
vim.keymap.set("x", "[SubLeader]s", ":s/\\%V", { noremap = true, silent = false })

-- Undoable<C-w> <C-u>
vim.keymap.set("i", "<C-w>", "<C-g>u<C-w>", { noremap = true, silent = true })
vim.keymap.set("i", "<C-u>", "<C-g>u<C-u>", { noremap = true, silent = true })

-- Change current directory
set_keymaps({
	"[SubLeader]cd",
	"<Cmd>lcd %:p:h<CR>:pwd<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Change current directory",
})

-- Delete all marks
set_keymaps({
	"[SubLeader]md",
	"<Cmd>delmarks!<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Delete all marks",
})

-- Change encoding
set_keymaps({
	"[SubLeader]eu",
	"<Cmd>e ++enc=utf-8<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Change encoding to UTF-8",
}, {
	"[SubLeader]es",
	"<Cmd>e ++enc=cp932<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Change encoding to CP932",
}, {
	"[SubLeader]ee",
	"<Cmd>e ++enc=euc-jp<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Change encoding to EUC-JP",
}, {
	"[SubLeader]ej",
	"<Cmd>e ++enc=iso-2022-jp<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Change encoding to ISO-2022-JP",
})

-- tags jump
set_keymaps({
	"<C-]>",
	"g<C-]>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Jump to the definition of the keyword under the cursor",
})

-- goto
set_keymaps({
	"gf",
	"gF",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Edit the file whose name is under or after the cursor",
}, {
	"<C-w>f",
	"<C-w>F",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Split current window in two and Edit the file name under cursor",
})

vim.keymap.set("n", "<C-w>f", "<C-w>F", { noremap = true, silent = true })
vim.keymap.set("n", "<C-w>gf", "<C-w>F", { noremap = true, silent = true })
vim.keymap.set("n", "<C-w><C-f>", "<C-w>F", { noremap = true, silent = true })
vim.keymap.set("n", "<C-w>g<C-f>", "<C-w>F", { noremap = true, silent = true })

-- split goto
vim.keymap.set("n", "-gf", "<Cmd>split<CR>gF", { noremap = true, silent = true })
vim.keymap.set("n", "<Bar>gf", "<Cmd>vsplit<CR>gF", { noremap = true, silent = true })
vim.keymap.set("n", "-<C-]>", "<Cmd>split<CR>g<C-]>", { noremap = true, silent = true })
vim.keymap.set("n", "<Bar><C-]>", "<Cmd>vsplit<CR>g<C-]>", { noremap = true, silent = true })

-- split
set_keymaps({
	"--",
	"<Cmd>split<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Split horizontally",
}, {
	"<Bar><Bar>",
	"<Cmd>vsplit<CR>",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Split vertically",
})

-- useful search
vim.keymap.set("n", "n", "'Nn'[v:searchforward]", { noremap = true, silent = true, expr = true })
vim.keymap.set("n", "N", "'nN'[v:searchforward]", { noremap = true, silent = true, expr = true })
vim.keymap.set("c", "<C-s>", "<HOME><Bslash><lt><END><Bslash>>", { noremap = true, silent = false })
vim.keymap.set("c", "<C-d>", "<HOME><Del><Del><END><BS><BS>", { noremap = true, silent = false })

-- Edit macro
vim.keymap.set(
	"n",
	"[SubLeader]me",
	":<C-r><C-r>='let @'. v:register .' = '. string(getreg(v:register))<CR><C-f><left>",
	{ noremap = true, silent = true }
)

-- indent
vim.keymap.set("x", "<", "<gv", { noremap = true, silent = true })
vim.keymap.set("x", ">", ">gv", { noremap = true, silent = true })
vim.keymap.set("n", "[[", "[m", { noremap = true, silent = true })
vim.keymap.set("n", "]]", "]m", { noremap = true, silent = true })

set_keymaps({
	"(",
	"{",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Paragraphs backward",
}, {
	")",
	"}",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Paragraphs forward",
})

-- command mode
vim.keymap.set("c", "<C-x>", "<C-r>=expand('%:p:h')<CR>/", { noremap = true, silent = false }) -- expand path
vim.keymap.set("c", "<C-z>", "<C-r>=expand('%:p:r')<CR>", { noremap = true, silent = false }) -- expand file (not ext)
vim.keymap.set("c", "<C-p>", "<Up>", { noremap = true, silent = false })
vim.keymap.set("c", "<C-n>", "<Down>", { noremap = true, silent = false })
vim.o.cedit = "<C-c>" -- command window

-- terminal mode
vim.keymap.set("t", "<Esc>", "<C-\\><C-n>", { noremap = true, silent = false })

-- fold
set_keymaps({
	"gzO",
	"zO",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Open all folds under the cursor recursively",
}, {
	"gzc",
	"zc",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Close one fold under the cursor",
}, {
	"gzC",
	"zC",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Close all folds under the cursor recursively",
}, {
	"gzR",
	"zR",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Open all folds",
}, {
	"gzM",
	"zM",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Close all folds",
}, {
	"gza",
	"za",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Toggle a fold",
}, {
	"gzA",
	"zA",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Toggle folds recursively",
})

vim.keymap.set("n", "gz<Space>", "zMzvzz", { noremap = true, silent = true })

-- quit
vim.keymap.set("n", "ZZ", "<Nop>", { noremap = true, silent = true })
vim.keymap.set("n", "ZQ", "<Nop>", { noremap = true, silent = true })

-- operator
vim.keymap.set("o", "<Space>", "iw", { noremap = true, silent = true })
vim.keymap.set("o", 'a"', '2i"', { noremap = true, silent = true })
vim.keymap.set("o", "a'", "2i'", { noremap = true, silent = true })
vim.keymap.set("o", "a`", "2i`", { noremap = true, silent = true })
-- -> In double-quote, you can't delete with ]} and ])
vim.keymap.set("o", "{", "[{i{<Esc>", { noremap = true, silent = true })
vim.keymap.set("o", "(", "[(i(<Esc>", { noremap = true, silent = true })
vim.keymap.set("o", "[", "T[", { noremap = true, silent = true })
vim.keymap.set("o", "<", "T<", { noremap = true, silent = true })
vim.keymap.set("n", "<<", "<<", { noremap = true, silent = true })
vim.keymap.set("o", "}", "]}", { noremap = true, silent = true })
vim.keymap.set("o", ")", "])", { noremap = true, silent = true })
vim.keymap.set("o", "]", "t]", { noremap = true, silent = true })
vim.keymap.set("o", ">", "t>", { noremap = true, silent = true })
vim.keymap.set("n", ">>", ">>", { noremap = true, silent = true })
vim.keymap.set("o", '"', 't"', { noremap = true, silent = true })
vim.keymap.set("o", "'", "t'", { noremap = true, silent = true })
vim.keymap.set("o", "`", "t`", { noremap = true, silent = true })
vim.keymap.set("o", "_", "t_", { noremap = true, silent = true })
vim.keymap.set("o", "-", "t-", { noremap = true, silent = true })

-- from monaqa's vimrc
set_keymaps({
	"[SubLeader])",
	"])",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Go to next unmatched ')'",
}, {
	"[SubLeader]}",
	"]}",
	mode = { "n" },
	opts = { noremap = true, silent = true },
	description = "Go to next unmatched '}'",
})

vim.keymap.set("x", "[SubLeader]]", "i]o``", { noremap = true, silent = true })
vim.keymap.set("x", "[SubLeader](", "i)``", { noremap = true, silent = true })
vim.keymap.set("x", "[SubLeader]{", "i}``", { noremap = true, silent = true })
vim.keymap.set("x", "[SubLeader][", "i]``", { noremap = true, silent = true })
vim.keymap.set("n", "d[SubLeader]]", "vi]o``d", { noremap = true, silent = true })
vim.keymap.set("n", "d[SubLeader](", "vi)o``d", { noremap = true, silent = true })
vim.keymap.set("n", "d[SubLeader]{", "vi}o``d", { noremap = true, silent = true })
vim.keymap.set("n", "d[SubLeader][", "vi]o``d", { noremap = true, silent = true })
vim.keymap.set("n", "d[SubLeader]]", "vi]o``d", { noremap = true, silent = true })
vim.keymap.set("n", "c[SubLeader]]", "vi]o``c", { noremap = true, silent = true })
vim.keymap.set("n", "c[SubLeader](", "vi)o``c", { noremap = true, silent = true })
vim.keymap.set("n", "c[SubLeader]{", "vi}o``c", { noremap = true, silent = true })
vim.keymap.set("n", "c[SubLeader][", "vi]o``c", { noremap = true, silent = true })
vim.keymap.set("n", "c[SubLeader]]", "vi]o``c", { noremap = true, silent = true })

-- control code
vim.keymap.set("i", "<C-q>", "<C-r>=nr2char(0x)<Left>", { noremap = true, silent = true })
vim.keymap.set("x", ".", ":normal! .<CR>", { noremap = true, silent = true })
vim.keymap.set(
	"x",
	"@",
	":<C-u>execute \":'<,'>normal! @\" . nr2char(getchar())<CR>",
	{ noremap = true, silent = true }
)

-- which-key
set_keymaps({
	"g<CR>",
	"<Cmd>WhichKey g<CR>",
	mode = { "n" },
	opts = { noremap = true },
	description = "WhichKey g",
}, {
	"[<CR>",
	"<Cmd>WhichKey [<CR>",
	mode = { "n" },
	opts = { noremap = true },
	description = "WhichKey [",
}, {
	"]<CR>",
	"<Cmd>WhichKey ]<CR>",
	mode = { "n" },
	opts = { noremap = true },
	description = "WhichKey ]",
})

-- legendary
vim.keymap.set("n", "<Leader>P", "<Cmd>Legendary<CR>", { noremap = true, silent = true })

if next(keymaps) ~= nil then
	-- if keymaps are not empty
	legendary.bind_keymaps(keymaps)
end