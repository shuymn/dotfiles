local null_ls = require("null-ls")

-- ref: https://github.com/jose-elias-alvarez/null-ls.nvim/wiki/Avoiding-LSP-formatting-conflicts
local lsp_disable = {
	["sumneko_lua"] = true,
}

local lsp_formatting = function(bufnr)
	vim.lsp.buf.format({
		filter = function(clients)
			-- filter out clients that you don't want to use
			return vim.tbl_filter(function(client)
				if lsp_disable[client.name] then
					return false
				else
					return true
				end
			end, clients)
		end,
		bufnr = bufnr,
	})
end

local augroup = vim.api.nvim_create_augroup("LspFormatting", {})

null_ls.setup({
	sources = {
		null_ls.builtins.formatting.stylua,
		null_ls.builtins.formatting.goimports,
		null_ls.builtins.formatting.prettier,
		null_ls.builtins.code_actions.gitsigns,
	},
	on_attach = function(client, bufnr)
		if client.supports_method("textDocument/formatting") then
			vim.api.nvim_clear_autocmds({ group = augroup, buffer = bufnr })
			vim.api.nvim_create_autocmd("BufWritePre", {
				group = augroup,
				buffer = bufnr,
				callback = function()
					lsp_formatting(bufnr)
				end,
			})
		end
	end,
})
