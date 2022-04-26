vim.g.mapleader = " "
vim.gmaplocalleader = "\\"

vim.o.shada = "'50,<1000,s100,\"1000,!"
vim.o.shadafile = vim.fn.stdpath("data") .. "/shada/main.shada"
vim.fn.mkdir(vim.fn.fnamemodify(vim.fn.expand(vim.g.viminfofile), ":h"), "p")
vim.o.shellslash = true
vim.o.complete = vim.o.complete .. ",k"
vim.o.completeopt = "menuone,noselect,noinsert"
vim.o.history = 10000
vim.o.timeout = true
vim.o.timeoutlen = 500
vim.o.ttimeoutlen = 10
vim.o.updatetime = 2000

-- tab
vim.o.tabstop = 4
vim.o.shiftwidth = 4
vim.o.softtabstop = 0
vim.o.expandtab = true

-- input
vim.o.backspace = "indent,eol,start"
vim.o.formatoptions = vim.o.formatoptions .. "m"
vim.o.fixendofline = false

-- command completion
vim.o.wildmenu = true
vim.o.wildmode = "longest,list,full"

-- search
vim.o.wrapscan = true
vim.o.ignorecase = true
vim.o.smartcase = true
vim.o.incsearch = true
vim.o.hlsearch = true

-- window
vim.o.splitbelow = true
vim.o.splitright = true

-- file
vim.o.autoread = true
vim.o.swapfile = false
vim.o.hidden = true
vim.o.backup = true
vim.o.backupdir = vim.fn.stdpath("data") .. "/backup/"
vim.fn.mkdir(vim.o.backupdir, "p")
vim.o.backupskip = ""
vim.o.directory = vim.fn.stdpath("data") .. "/swap/"
vim.fn.mkdir(vim.o.directory, "p")
vim.o.updatecount = 100
vim.o.undofile = true
vim.o.undodir = vim.fn.stdpath("data") .. "/undo/"
vim.fn.mkdir(vim.o.undodir, "p")
vim.o.modeline = false

-- clipboard
vim.o.clipboard = "unnamedplus,unnamed," .. vim.o.clipboard

-- mouse
vim.o.mouse = "a"

-- beep
vim.o.errorbells = false
vim.o.visualbell = false

-- tags
vim.opt.tags:remove({ "./tags" })
vim.opt.tags:remove({ "./tags;" })
vim.opt.tags = "./tags," .. vim.go.tags

-- session
vim.o.sessionoptions = "buffers,curdir,tabpages,winsize"

-- quickfix
vim.o.switchbuf = "useopen,uselast"

vim.o.pumblend = 0
vim.o.wildoptions = vim.o.wildoptions .. ",pum"
 vim.opt.spelllang = { "en", "cjk" }
vim.o.inccommand = "split"
vim.g.vimsyn_embed = "l"

-- diff
vim.o.diffopt = vim.o.diffopt .. ",vertical,internal,algorithm:patience,iwhite,indent-heuristic"
