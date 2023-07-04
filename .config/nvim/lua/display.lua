-- nvim color
vim.env.NVIM_TUI_ENABLE_TRUE_COLOR = 1

vim.o.synmaxcol = 200

-- colorscheme
vim.cmd.syntax("enable")
vim.o.t_Co = 256
vim.o.background = "dark"

-- true color support
vim.g.colorterm = os.getenv("COLORTERM")
if
	vim.g.colorterm == "truecolor"
	or vim.g.colorterm == "24bit"
	or vim.g.colorterm == "rxvt"
	or vim.g.colorterm == ""
then
	if vim.fn.exists("+termguicolors") then
		vim.o.t_8f = "<Esc>[38;2;%lu;%lu;%lum"
		vim.o.t_8b = "<Esc>[48;2;%lu;%lu;%lum"
		vim.o.termguicolors = true
	end
end

-- colorscheme plugins -> colorscheme
vim.o.cursorline = true

vim.o.display = "lastline"
vim.o.showmode = false
vim.o.showmatch = true
vim.o.matchtime = 1
vim.o.showcmd = true
vim.o.number = true
vim.o.relativenumber = true
vim.o.wrap = true
vim.o.title = false
vim.o.scrolloff = 5
vim.o.sidescrolloff = 5
vim.o.pumheight = 10

-- folding
vim.o.foldmethod = "manual"
vim.o.foldlevel = 1
vim.o.foldlevelstart = 99
vim.w.foldcolumn = "0:"

-- cursor style
vim.o.guicursor = "n-v-c:block-Cursor/lCursor-blinkon0,i-ci:ver25-Cursor/lCursor,r-cr:hor20-Cursor/lCursor"
vim.o.cursorlineopt = "number"

-- status line
vim.o.laststatus = 3
vim.o.shortmess = "aItToOF"
vim.opt.fillchars = {
	horiz = "━",
	horizup = "┻",
	horizdown = "┳",
	vert = "┃",
	vertleft = "┫",
	vertright = "┣",
	verthoriz = "╋",
}
