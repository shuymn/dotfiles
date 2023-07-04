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

vim.keymap.set({ "n", "v" }, "<Space>", "<Nop>", { silent = true })

-- <Leader>
vim.keymap.set("n", "<Leader><CR>", "<Cmd>WhichKey \\ <CR>", { noremap = true })

-- <LocalLeader>
vim.keymap.set("n", "<LocalLeader><CR>", "<Cmd>WhichKey <LocalLeader><CR>", { noremap = true })

-- [SubLeader]
vim.keymap.set({ "n", "x" }, "[SubLeader]", "<Nop>", { noremap = true, silent = true })
vim.keymap.set({ "n", "x" }, ",", "<Nop>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", ",", "[SubLeader]", {})
vim.api.nvim_set_keymap("x", ",", "[SubLeader]", {})

-- not use
vim.keymap.set("n", "qq", function()
	return vim.fn.reg_recording() == "" and "qq" or "q"
end, { noremap = true, expr = true })
vim.keymap.set("n", "q", "<Cmd>close<CR>", { noremap = true, silent = true })

-- move cursor
vim.keymap.set({ "n", "x" }, "j", function()
	return vim.v.count > 0 and "j" or "gj"
end, { silent = true, expr = true })
vim.keymap.set({ "n", "x" }, "k", function()
	return vim.v.count > 0 and "k" or "gk"
end, { silent = true, expr = true })

-- jump cursor
-- Automatically indent with i and A made by ycino
vim.keymap.set("n", "i", function()
	return vim.fn.len(vim.fn.getline(".")) ~= 0 and "i" or '"_cc'
end, { noremap = true, expr = true, silent = true })
vim.keymap.set("n", "A", function()
	return vim.fn.len(vim.fn.getline(".")) ~= 0 and "A" or '"_cc'
end, { noremap = true, expr = true, silent = true })

-- undo behavior
vim.keymap.set("i", "<BS>", "<C-g>u<BS>", { noremap = true, silent = false })
vim.keymap.set("i", "<CR>", "<C-g>u<CR>", { noremap = true, silent = false })
vim.keymap.set("i", "<DEL>", "<C-g>u<DEL>", { noremap = true, silent = false })

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

-- paste
vim.keymap.set({ "n", "x" }, "p", "]p", { noremap = true, silent = true })

-- xはレジスタに登録しない
vim.keymap.set({ "n", "x" }, "x", '"_x', { noremap = true, silent = true })

-- clear highlighting
vim.keymap.set("n", "<Esc>", "<Cmd>nohlsearch<CR><C-L><Esc>", { noremap = true, silent = true })

-- For search
vim.keymap.set("n", "g/", "/\\v", { noremap = true, silent = false })
vim.keymap.set("n", "*", "g*N", { noremap = true, silent = true })
vim.keymap.set("x", "*", 'y/<C-R>"<CR>N', { noremap = true, silent = true })
vim.keymap.set("x", "/", "<ESC>/\\%V", { noremap = true, silent = false })
vim.keymap.set("x", "?", "<ESC>?\\%V", { noremap = true, silent = false })

-- Undoable<C-w> <C-u>
vim.keymap.set("i", "<C-w>", "<C-g>u<C-w>", { noremap = true, silent = true })
vim.keymap.set("i", "<C-u>", "<C-g>u<C-u>", { noremap = true, silent = true })

-- split
vim.keymap.set("n", "--", "<Cmd>split<CR>", { noremap = true, silent = true })
vim.keymap.set("n", "<Bar><Bar>", "<Cmd>vsplit<CR>", { noremap = true, silent = true })

-- useful search
vim.keymap.set("n", "n", "'Nn'[v:searchforward]", { noremap = true, silent = true, expr = true })
vim.keymap.set("n", "N", "'nN'[v:searchforward]", { noremap = true, silent = true, expr = true })

-- indent
vim.keymap.set("x", "<", "<gv", { noremap = true, silent = true })
vim.keymap.set("x", ">", ">gv", { noremap = true, silent = true })

-- command mode
vim.keymap.set("c", "<C-x>", "<C-r>=expand('%:p:h')<CR>/", { noremap = true, silent = false }) -- expand path
vim.keymap.set("c", "<C-z>", "<C-r>=expand('%:p:r')<CR>", { noremap = true, silent = false }) -- expand file (not ext)
vim.keymap.set("c", "<C-p>", "<Up>", { noremap = true, silent = false })
vim.keymap.set("c", "<C-n>", "<Down>", { noremap = true, silent = false })
vim.o.cedit = "<C-c>" -- command window
