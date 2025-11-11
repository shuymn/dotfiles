-- load defaults i.e lua_lsp
require("nvchad.configs.lspconfig").defaults()

local servers = { "gopls" }
vim.lsp.enable(servers)
