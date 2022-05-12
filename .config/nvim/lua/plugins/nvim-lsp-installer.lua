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
	buf_set_keymap("n", "gD", "<cmd>lua vim.lsp.buf.declaration()<CR>", opts)
	buf_set_keymap("n", "gd", "<cmd>lua vim.lsp.buf.definition()<CR>", opts)
	buf_set_keymap("n", "?", "<cmd>lua vim.lsp.buf.hover()<CR>", opts)
	buf_set_keymap("n", "gi", "<cmd>lua vim.lsp.buf.implementation()<CR>", opts)
	buf_set_keymap("n", "g?", "<cmd>lua vim.lsp.buf.signature_help()<CR>", opts)
	buf_set_keymap("n", "[lsp]wa", "<cmd>lua vim.lsp.buf.add_workspace_folder()<CR>", opts)
	buf_set_keymap("n", "[lsp]wr", "<cmd>lua vim.lsp.buf.remove_workspace_folder()<CR>", opts)
	buf_set_keymap("n", "[lsp]wl", "<cmd>lua print(vim.inspect(vim.lsp.buf.list_workspace_folders()))<CR>", opts)
	buf_set_keymap("n", "[lsp]D", "<cmd>lua vim.lsp.buf.type_definition()<CR>", opts)
	buf_set_keymap("n", "[lsp]rn", "<cmd>lua vim.lsp.buf.rename()<CR>", opts)
	buf_set_keymap("n", "[lsp]a", "<cmd>lua vim.lsp.buf.code_action()<CR>", opts)
	buf_set_keymap("n", "gr", "<cmd>lua vim.lsp.buf.references()<CR>", opts)
	buf_set_keymap("n", "[lsp]e", "<cmd>lua vim.diagnostic.open_float()<CR>", opts)
	buf_set_keymap("n", "[d", "<cmd>lua vim.diagnostic.goto_prev()<CR>", opts)
	buf_set_keymap("n", "]d", "<cmd>lua vim.diagnostic.goto_next()<CR>", opts)
	buf_set_keymap("n", "[lsp]q", "<cmd>lua vim.diagnostic.setloclist()<CR>", opts)
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
				telemetry = { enable = false },
			},
		},
	},
	["gopls"] = {
		cmd = { "gopls", "serve" },
		filetypes = { "go", "gomod" },
		root_dir = util.root_pattern("go.work", "go.mod", ".git"),
		settings = {
			gopls = {
				staticcheck = false,
			},
		},
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
