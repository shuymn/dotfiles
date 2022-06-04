local on_attach = function(client, bufnr)
	local function buf_set_keymap(...)
		vim.api.nvim_buf_set_keymap(bufnr, ...)
	end
	local function buf_set_option(...)
		vim.api.nvim_buf_set_option(bufnr, ...)
	end

	-- Enable completion triggered by <c-x><c-o>
	buf_set_option("omnifunc", "v:lua.vim.lsp.omnifunc")

	-- mappings
	local opts = { noremap = true, silent = true }

	-- See `:help vim.lsp.*` for documentation on any of the below functions
	buf_set_keymap("n", "[lsp]D", "<cmd>lua vim.lsp.buf.declaration()<CR>", opts)
	buf_set_keymap("n", "[lsp]d", "<cmd>lua vim.lsp.buf.definition()<CR>", opts)
	buf_set_keymap("n", "?", "<cmd>Lspsaga hover_doc<CR>", opts)
	buf_set_keymap("n", "[lsp]i", "<cmd>lua vim.lsp.buf.implementation()<CR>", opts)
	buf_set_keymap("n", "[lsp]?", "<cmd>lua vim.lsp.buf.signature_help()<CR>", opts)
	buf_set_keymap("n", "[lsp]t", "<cmd>lua vim.lsp.buf.type_definition()<CR>", opts)
	buf_set_keymap("n", "[lsp]R", "<cmd>Lspsaga rename<CR>", opts)
	buf_set_keymap("n", "[lsp]a", "<cmd>Lspsaga code_action<CR>", opts)
	buf_set_keymap("n", "[lsp]r", "<cmd>lua vim.lsp.buf.references()<CR>", opts)
	buf_set_keymap("n", "[lsp]e", "<cmd>lua vim.diagnostic.open_float()<CR>", opts)
	buf_set_keymap("n", "[lsp]j", "<cmd>Lspsaga diagnostic_jump_next<CR>", opts)
	buf_set_keymap("n", "[lsp]k", "<cmd>Lspsaga diagnostic_jump_prev<CR>", opts)
	buf_set_keymap("n", "[lsp]J", "<cmd>lua require('lspsaga.action').smart_scroll_with_saga(-1)<cr>", opts)
	buf_set_keymap("n", "[lsp]K", "<cmd>lua require('lspsaga.action').smart_scroll_with_saga(1)<cr>", opts)
	buf_set_keymap("n", "[lsp]L", "<cmd>lua vim.diagnostic.setloclist()<CR>", opts)
	buf_set_keymap("n", "[lsp]l", "<cmd>Lspsaga show_line_diagnostics<CR>", opts)
	buf_set_keymap("n", "[lsp]f", "<cmd>lua vim.lsp.buf.formatting()<CR>", opts)

	require("illuminate").on_attach(client)
end

local util = require("lspconfig/util")

local server_configs = {
	["sumneko_lua"] = {
		settings = {
			Lua = {
				format = {
					enable = false,
				},
				workspace = {
					preloadFileSize = 500,
				},
				runtime = {
					version = "LuaJIT",
				},
				diagnostics = {
					globals = { "vim" },
					disable = { "different-requires" },
				},
				telemetry = { enable = false },
			},
		},
	},
	["gopls"] = {
		cmd = { "gopls", "serve" },
		filetypes = { "go", "gomod" },
		root_dir = util.root_pattern("go.work", "go.mod", ".git"),
	},
	["golangcilsp"] = {
		filetypes = { "go" },
		default_config = {
			cmd = { "golangci-lint-langserver" },
			root_dir = util.root_pattern(".git", "go.mod"),
			init_options = {
				command = { "golangci-lint", "run", "--out-format", "json" },
			},
		},
	},
	["volar"] = {
		autostart = false,
	},
	["vuels"] = {
		autostart = false,
	},
}

local lsp_installer = require("nvim-lsp-installer")
local capabilities = require("cmp_nvim_lsp").update_capabilities(vim.lsp.protocol.make_client_capabilities())

lsp_installer.on_server_ready(function(server)
	local opts = { capabilities = capabilities, on_attach = on_attach }
	if server_configs[server.name] then
		opts = vim.tbl_deep_extend("force", opts, server_configs[server.name])
	end
	server:setup(opts)
	vim.cmd([[ do User LspAttachBuffers ]])
end)
