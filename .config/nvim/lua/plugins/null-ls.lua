local null_ls = require("null-ls")

null_ls.setup({
	sources = {
		null_ls.builtins.formatting.stylua,
		null_ls.builtins.formatting.goimports,
		null_ls.builtins.code_actions.gitsigns,
	},
	on_attach = function(client)
		if client.resolved_capabilities.document_formatting then
			vim.cmd([[
			augroup LspFormatting
				autocmd! * <buffer>
				autocmd BufWritePre <buffer> lua vim.lsp.buf.formatting_seq_sync()
			augroup END
			]])
		end
	end,
})
