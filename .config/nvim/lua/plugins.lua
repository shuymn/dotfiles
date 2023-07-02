local install_path = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"

if not vim.loop.fs_stat(install_path) then
	vim.fn.system({
		"git",
		"clone",
		"--filter=blob:none",
		"https://github.com/folke/lazy.nvim.git",
		"--branch=stable",
		install_path,
	})
end

vim.opt.rtp:prepend(install_path)

return require("lazy").setup({
	-- vim script library
	"tpope/vim-repeat",

	-- lua library
	"nvim-lua/popup.nvim",
	"nvim-lua/plenary.nvim",
	"tami5/sqlite.lua",
	"MunifTanjim/nui.nvim",

	-- font
	"nvim-tree/nvim-web-devicons",

	-- colorscheme
	{
		"catppuccin/nvim",
		name = "catppuccin",
		priority = 1000,
		config = function()
			require("catppuccin").setup({
				flavour = "mocha",
				integrations = {
					fidget = true,
					lsp_saga = true,
					mason = true,
					noice = true,
					treesitter_context = true,
					lsp_trouble = true,
					illuminate = true,
					which_key = true,
				},
			})

			vim.cmd([[colorscheme catppuccin]])
		end,
	},

	-- auto completion
	{
		"hrsh7th/nvim-cmp",
		event = "InsertEnter",
		dependencies = {
			{
				"L3MON4D3/LuaSnip",
				dependencies = {
					"rafamadriz/friendly-snippets",
				},
				config = function()
					local ls = require("luasnip")
					local types = require("luasnip.util.types")

					ls.config.set_config({
						history = true,
						updateevents = "TextChanged,TextChangedI",
						delete_check_events = "TextChanged",
						ext_opts = { [types.choiceNode] = { active = { virt_text = { { "choiceNode", "Comment" } } } } },
						ext_base_prio = 300,
						ext_prio_increase = 1,
						enable_autosnippets = true,
						store_selection_keys = "<Tab>",
						ft_func = function()
							return vim.split(vim.bo.filetype, ".", true)
						end,
					})

					require("luasnip.loaders.from_vscode").lazy_load()
					require("luasnip.loaders.from_lua").lazy_load({ paths = "~/.config/nvim/luasnip-snippets" })
				end,
			},
			{
				"onsails/lspkind.nvim",
				config = function()
					require("lspkind").init({
						mode = "symbol_text",
					})
				end,
			},
			"hrsh7th/cmp-nvim-lsp",
			"hrsh7th/cmp-nvim-lsp-signature-help",
			"hrsh7th/cmp-nvim-lsp-document-symbol",
			"hrsh7th/cmp-buffer",
			"hrsh7th/cmp-path",
			"hrsh7th/cmp-nvim-lua",
			"saadparwaiz1/cmp_luasnip",
			"hrsh7th/cmp-omni",
			"hrsh7th/cmp-calc",
			"hrsh7th/cmp-emoji",
			"f3fora/cmp-spell",
			{
				"uga-rosa/cmp-dictionary",
				config = function()
					local file = "/usr/share/dict/words"
					local dic = {}
					if vim.fn.filereadable(file) ~= 0 then
						dic = file
					end

					require("cmp_dictionary").setup({
						dic = { ["*"] = dic },
						exact = 2,
						async = false,
						capacity = 5,
						debug = false,
					})
				end,
			},
			"ray-x/cmp-treesitter",
			"hrsh7th/cmp-cmdline",
		},
		config = function()
			vim.opt.completeopt = { "menu", "menuone", "noselect" }

			local cmp = require("cmp")
			local types = require("cmp.types")
			local luasnip = require("luasnip")

			local has_words_before = function()
				local line, col = unpack(vim.api.nvim_win_get_cursor(0))
				return col ~= 0
					and vim.api.nvim_buf_get_lines(0, line - 1, line, true)[1]:sub(col, col):match("%s") == nil
			end

			cmp.setup({
				formatting = {
					format = require("lspkind").cmp_format({
						with_text = true,
						menu = {
							buffer = "[Buffer]",
							nvim_lsp = "[LSP]",
							luasnip = "[LuaSnip]",
							nvim_lua = "[Lua]",
							path = "[Path]",
							omni = "[Omni]",
							spell = "[Spell]",
							emoji = "[Emoji]",
							calc = "[Calc]",
							treesitter = "[TS]",
							dictionary = "[Dict]",
							mocword = "[Mocword]",
						},
					}),
				},
				snippet = {
					expand = function(args)
						luasnip.lsp_expand(args.body)
					end,
				},
				sorting = {
					comparators = {
						cmp.config.compare.offset,
						cmp.config.compare.exact,
						cmp.config.compare.score,
						function(entry1, entry2)
							local kind1 = entry1:get_kind()
							kind1 = kind1 == types.lsp.CompletionItemKind.Text and 100 or kind1
							local kind2 = entry2:get_kind()
							kind2 = kind2 == types.lsp.CompletionItemKind.Text and 100 or kind2
							if kind1 ~= kind2 then
								if kind1 == types.lsp.CompletionItemKind.Snippet then
									return false
								end
								if kind2 == types.lsp.CompletionItemKind.Snippet then
									return true
								end
								local diff = kind1 - kind2
								if diff < 0 then
									return true
								elseif diff > 0 then
									return false
								end
							end
						end,
						cmp.config.compare.sort_text,
						cmp.config.compare.length,
						cmp.config.compare.order,
					},
				},
				mapping = {
					["<C-p>"] = cmp.mapping(cmp.mapping.select_prev_item(), { "i", "c" }),
					["<C-n>"] = cmp.mapping(cmp.mapping.select_next_item(), { "i", "c" }),
					["<C-b>"] = cmp.mapping(cmp.mapping.scroll_docs(-4), { "i", "c" }),
					["<C-f>"] = cmp.mapping(cmp.mapping.scroll_docs(4), { "i", "c" }),
					["<C-Space>"] = cmp.mapping(cmp.mapping.complete(), { "i", "c" }),
					["<C-y>"] = cmp.config.disable,
					["<C-q>"] = cmp.mapping({ i = cmp.mapping.abort(), c = cmp.mapping.close() }),
					["<CR>"] = cmp.mapping.confirm({ select = false }),
					["<Tab>"] = cmp.mapping(function(fallback)
						if cmp.visible() then
							cmp.select_next_item()
						elseif luasnip.expand_or_jumpable() then
							luasnip.expand_or_jump()
						elseif has_words_before() then
							cmp.complete()
						else
							fallback()
						end
					end, { "i", "s" }),
					["<S-Tab>"] = cmp.mapping(function(fallback)
						if cmp.visible() then
							cmp.select_prev_item()
						elseif luasnip.jumpable(-1) then
							luasnip.jump(-1)
						else
							fallback()
						end
					end, { "i", "s" }),
				},
				sources = cmp.config.sources({
					{ name = "nvim_lsp", priority = 100 },
					{ name = "luasnip", priority = 20 },
					{ name = "path", priority = 100 },
					{ name = "emoji", insert = true, priority = 60 },
					{ name = "nvim_lua", priority = 50 },
					{ name = "nvim_lsp_signature_help", priority = 80 },
				}, {
					{ name = "buffer", priority = 50 },
					{ name = "omni", priority = 40 },
					{ name = "spell", priority = 40 },
					{ name = "calc", priority = 50 },
					{ name = "treesitter", priority = 30 },
					{ name = "dictionary", keyword_length = 2, priority = 10 },
				}),
			})

			cmp.setup.filetype({ "gitcommit", "markdown" }, {
				sources = cmp.config.sources({
					{ name = "nvim_lsp", priority = 100 },
					{ name = "luasnip", priority = 80 },
					{ name = "path", priority = 100 },
					{ name = "emoji", insert = true, priority = 60 },
				}, {
					{ name = "buffer", priority = 50 },
					{ name = "omni", priority = 40 },
					{ name = "spell", priority = 40 },
					{ name = "calc", priority = 50 },
					{ name = "treesitter", priority = 30 },
					{ name = "mocword", priority = 60 },
					{ name = "dictionary", keyword_length = 2, priority = 10 },
				}),
			})

			cmp.setup.cmdline("/", {
				mapping = cmp.mapping.preset.cmdline(),
				sources = cmp.config.sources({
					{ name = "nvim_lsp_document_symbol" },
				}, {
					{ name = "buffer" },
				}),
			})

			cmp.setup.cmdline(":", {
				mapping = {
					["<Tab>"] = cmp.mapping(function(fallback)
						if cmp.visible() then
							cmp.select_next_item()
						else
							fallback()
						end
					end, { "c" }),

					["<S-Tab>"] = cmp.mapping(function(fallback)
						if cmp.visible() then
							cmp.select_prev_item()
						else
							fallback()
						end
					end, { "c" }),
					["<C-y>"] = {
						c = cmp.mapping.confirm({ select = false }),
					},
					["<C-q>"] = {
						c = cmp.mapping.abort(),
					},
				},
				sources = cmp.config.sources({ { name = "path" } }, { { name = "cmdline" } }),
			})
		end,
	},
	{
		"nvim-treesitter/nvim-treesitter",
		dependencies = {
			"yioneko/nvim-yati",
			"p00f/nvim-ts-rainbow",
			"JoosepAlviste/nvim-ts-context-commentstring",
			"nvim-treesitter/nvim-treesitter-textobjects",
			{
				"mfussenegger/nvim-ts-hint-textobject",
				config = function()
					vim.api.nvim_set_keymap(
						"o",
						"m",
						"<Cmd><C-u>lua require('tsht').nodes()<CR>",
						{ noremap = false, silent = false }
					)
					vim.api.nvim_set_keymap(
						"x",
						"m",
						"<Cmd>lua require('tsht').nodes()<CR>",
						{ noremap = true, silent = false }
					)
				end,
			},
			{
				"David-Kunz/treesitter-unit",
				config = function()
					vim.keymap.set("x", "iu", ':lua require"treesitter-unit".select()<CR>', { noremap = true })
					vim.keymap.set("x", "au", ':lua require"treesitter-unit".select(true)<CR>', { noremap = true })
					vim.keymap.set("o", "iu", ':<c-u>lua require"treesitter-unit".select()<CR>', { noremap = true })
					vim.keymap.set("o", "au", ':<c-u>lua require"treesitter-unit".select(true)<CR>', { noremap = true })
				end,
			},
		},
		config = function()
			require("nvim-treesitter.configs").setup({
				ensure_installed = "all",
				ignore_install = { "phpdoc" },
				highlight = {
					enable = true,
					additional_vim_regex_highlighting = false,
				},
				incremental_selection = {
					enable = true,
					keymaps = {
						init_selection = "<CR>",
						scope_incremental = "<CR>",
						node_incremental = "<TAB>",
						node_decremental = "<S-TAB>",
					},
				},
				indent = { enable = false },
				textobjects = {
					select = {
						enable = true,
						disable = {},
						keymaps = {
							["af"] = "@function.outer",
							["if"] = "@function.inner",
							["ac"] = "@class.outer",
							["ic"] = "@class.inner",
							["iB"] = "@block.inner",
							["aB"] = "@block.outer",
							["ii"] = "@conditional.inner",
							["ai"] = "@conditional.outer",
							["il"] = "@loop.inner",
							["al"] = "@loop.outer",
							["ip"] = "@parameter.inner",
							["ap"] = "@parameter.outer",
						},
					},
					swap = {
						enable = true,
						swap_next = { ["'>"] = "@parameter.inner" },
						swap_previous = { ["'<"] = "@parameter.inner" },
					},
					move = {
						enable = true,
						goto_next_start = { ["]m"] = "@function.outer", ["]]"] = "@class.outer" },
						goto_next_end = { ["]M"] = "@function.outer", ["]["] = "@class.outer" },
						goto_previous_start = { ["[m"] = "@function.outer", ["[["] = "@class.outer" },
						goto_previous_end = { ["[M"] = "@function.outer", ["[]"] = "@class.outer" },
					},
				},
				rainbow = {
					enable = true,
					extended_mode = true,
					max_file_lines = nil,
				},
				matchup = { enable = true },
				context_commentstring = { enable = true },
				yati = { enable = true },
			})
		end,
	},

	-- lsp
	{
		{
			"neovim/nvim-lspconfig",
			config = function()
				local signs = { Error = "", Warn = "", Hint = "", Info = "" }

				for type, icon in pairs(signs) do
					local hl = "DiagnosticSign" .. type
					vim.fn.sign_define(hl, { text = icon, texthl = hl, numhl = hl })
				end
			end,
		},
		"weilbith/nvim-lsp-smag",
		{
			"williamboman/mason.nvim",
			config = function()
				require("mason").setup()
			end,
		},
		{
			"williamboman/mason-lspconfig.nvim",
			dependencies = {
				{
					"RRethy/vim-illuminate",
					config = function()
						vim.g.Illuminate_delay = 300
					end,
				},
			},
			config = function()
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
					buf_set_keymap(
						"n",
						"[lsp]J",
						"<cmd>lua require('lspsaga.action').smart_scroll_with_saga(-1)<cr>",
						opts
					)
					buf_set_keymap(
						"n",
						"[lsp]K",
						"<cmd>lua require('lspsaga.action').smart_scroll_with_saga(1)<cr>",
						opts
					)
					buf_set_keymap("n", "[lsp]L", "<cmd>lua vim.diagnostic.setloclist()<CR>", opts)
					buf_set_keymap("n", "[lsp]l", "<cmd>Lspsaga show_line_diagnostics<CR>", opts)
					buf_set_keymap("n", "[lsp]f", "<cmd>lua vim.lsp.buf.formatting()<CR>", opts)

					require("illuminate").on_attach(client)
				end

				local server_configs = {
					["lua_ls"] = {
						settings = {
							Lua = {
								format = { enable = false },
								workspace = { preloadFileSize = 500 },
								runtime = { version = "LuaJIT" },
								diagnostics = {
									globals = { "vim" },
									disable = { "different-requires" },
								},
								telemetry = { enable = false },
							},
						},
					},
					["volar"] = { autostart = false },
					["vuels"] = { autostart = false },
				}

				require("mason-lspconfig").setup({
					handlers = {
						function(server_name)
							local opts = {
								capabilities = require("cmp_nvim_lsp").default_capabilities(),
								on_attach = on_attach,
							}
							if server_configs[server_name] then
								opts = vim.tbl_deep_extend("force", opts, server_configs[server_name])
							end
							require("lspconfig")[server_name].setup(opts)
						end,
					},
				})
			end,
		},
		{
			"jay-babu/mason-null-ls.nvim",
			dependencies = "jose-elias-alvarez/null-ls.nvim",
			config = function()
				local null_ls = require("null-ls")

				-- ref: https://github.com/jose-elias-alvarez/null-ls.nvim/wiki/Avoiding-LSP-formatting-conflicts
				local lsp_disable = {
					["lua_ls"] = true,
				}

				local lsp_formatting = function(bufnr)
					vim.lsp.buf.format({
						filter = function(client)
							-- filter out client that you don't want to use
							if lsp_disable[client.name] then
								return false
							else
								return true
							end
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

				require("mason-null-ls").setup({
					ensure_installed = nil,
					automatic_installation = true,
				})
			end,
		},
		{
			"tamago324/nlsp-settings.nvim",
			config = function()
				require("nlspsettings").setup({
					config_home = vim.fn.stdpath("config") .. "/nlsp-settings",
					local_settings_dir = ".nvim/nlsp-settings",
					local_settings_root_markers = { ".git" },
					append_default_schemas = true,
					loader = "json",
					nvim_notify = {
						enable = true,
						timeout = 5000,
					},
				})
			end,
		},
	},
	{
		"nvimdev/lspsaga.nvim",
		config = function()
			require("lspsaga").setup({
				-- default
				debug = false,
				use_saga_diagnostic_sign = true,
				-- code action title icon
				code_action_prompt = { enable = true, sign = true, sign_priority = 40, virtual_text = true },
				max_preview_lines = 10,
				finder_action_keys = {
					open = "o",
					vsplit = "s",
					split = "i",
					quit = "q",
					scroll_down = "<C-f>",
					scroll_up = "<C-b>",
				},
				code_action_keys = { quit = "q", exec = "<CR>" },
				rename_action_keys = { quit = "<C-c>", exec = "<CR>" },
				border_style = "single",
				server_filetype_map = {},
				diagnostic_prefix_format = "%d. ",
				ui = {
					kind = require("catppuccin.groups.integrations.lsp_saga").custom_kind(),
				},
			})
		end,
	},
	{
		"folke/trouble.nvim",
		config = function()
			require("trouble").setup({
				position = "bottom", -- position of the list can be: bottom, top, left, right
				height = 10, -- height of the trouble list when position is top or bottom
				width = 50, -- width of the list when position is left or right
				icons = false, -- use devicons for filenames
				mode = "workspace_diagnostics", -- "workspace_diagnostics", "document_diagnostics", "quickfix", "lsp_references", "loclist"
				fold_open = "", -- icon used for open folds
				fold_closed = "", -- icon used for closed folds
				group = true, -- group results by file
				padding = true, -- add an extra new line on top of the list
				action_keys = { -- key mappings for actions in the trouble list
					-- map to {} to remove a mapping, for example:
					-- close = {},
					close = "q", -- close the list
					cancel = "<esc>", -- cancel the preview and get back to your last window / buffer / cursor
					refresh = "r", -- manually refresh
					jump = { "<cr>", "<tab>" }, -- jump to the diagnostic or open / close folds
					open_split = { "<c-x>" }, -- open buffer in new split
					open_vsplit = { "<c-v>" }, -- open buffer in new vsplit
					open_tab = { "<c-t>" }, -- open buffer in new tab
					jump_close = { "o" }, -- jump to the diagnostic and close the list
					toggle_mode = "m", -- toggle between "workspace" and "document" diagnostics mode
					toggle_preview = "P", -- toggle auto_preview
					hover = "K", -- opens a small popup with the full multiline message
					preview = "p", -- preview the diagnostic location
					close_folds = { "zM", "zm" }, -- close all folds
					open_folds = { "zR", "zr" }, -- open all folds
					toggle_fold = { "zA", "za" }, -- toggle fold of current file
					previous = "k", -- preview item
					next = "j", -- next item
				},
				indent_lines = true, -- add an indent guide below the fold icons
				auto_open = false, -- automatically open the list when you have diagnostics
				auto_close = false, -- automatically close the list when you have no diagnostics
				auto_preview = true, -- automatically preview the location of the diagnostic. <esc> to close preview and go back to last window
				auto_fold = false, -- automatically fold a file trouble list at creation
				auto_jump = { "lsp_definitions" }, -- for the given modes, automatically jump if there is only a single result
				signs = {
					-- icons / text used for a diagnostic
					error = "",
					warning = "",
					hint = "",
					information = "",
					other = "",
					use_diagnostic_signs = true, -- enabling this will use the signs defined in your lsp client
				},
			})
		end,
	},
	{
		"j-hui/fidget.nvim",
		branch = "legacy",
		config = function()
			require("fidget").setup({
				window = {
					blend = 0,
				},
				sources = {
					["null-ls"] = {
						ignore = true,
					},
				},
			})
		end,
	},

	-- fuzzy finder
	{
		"nvim-telescope/telescope.nvim",
		dependencies = {
			"nvim-telescope/telescope-frecency.nvim",
			"nvim-telescope/telescope-symbols.nvim",
		},
		config = function()
			require("telescope").load_extension("frecency")

			local actions = require("telescope.actions")
			local action_layout = require("telescope.actions.layout")
			local pickers = require("telescope.pickers")
			local finders = require("telescope.finders")
			local make_entry = require("telescope.make_entry")
			local utils = require("telescope.utils")
			local conf = require("telescope.config").values
			local telescope_builtin = require("telescope.builtin")
			local Path = require("plenary.path")

			local action_state = require("telescope.actions.state")
			local custom_actions = {}

			function custom_actions._multiopen(prompt_bufnr, open_cmd)
				local picker = action_state.get_current_picker(prompt_bufnr)
				local num_selections = #picker:get_multi_selection()
				if num_selections > 1 then
					vim.cmd("bw!")
					for _, entry in ipairs(picker:get_multi_selection()) do
						vim.cmd(string.format("%s %s", open_cmd, entry.value))
					end
					vim.cmd("stopinsert")
				else
					if open_cmd == "vsplit" then
						actions.file_vsplit(prompt_bufnr)
					elseif open_cmd == "split" then
						actions.file_split(prompt_bufnr)
					elseif open_cmd == "tabe" then
						actions.file_tab(prompt_bufnr)
					else
						actions.file_edit(prompt_bufnr)
					end
				end
			end

			function custom_actions.multi_selection_open_vsplit(prompt_bufnr)
				custom_actions._multiopen(prompt_bufnr, "vsplit")
			end
			function custom_actions.multi_selection_open_split(prompt_bufnr)
				custom_actions._multiopen(prompt_bufnr, "split")
			end
			function custom_actions.multi_selection_open_tab(prompt_bufnr)
				custom_actions._multiopen(prompt_bufnr, "tabe")
			end
			function custom_actions.multi_selection_open(prompt_bufnr)
				custom_actions._multiopen(prompt_bufnr, "edit")
			end

			require("telescope").setup({
				defaults = {
					vimgrep_arguments = {
						"rg",
						"--color=never",
						"--no-heading",
						"--with-filename",
						"--line-number",
						"--column",
						"--smart-case",
						"--hidden",
					},
					prompt_prefix = "> ",
					selection_caret = "> ",
					entry_prefix = "  ",
					initial_mode = "insert",
					selection_strategy = "reset",
					sorting_strategy = "ascending",
					layout_strategy = "flex",
					layout_config = {
						width = 0.8,
						horizontal = {
							mirror = false,
							prompt_position = "top",
							preview_cutoff = 120,
							preview_width = 0.5,
						},
						vertical = {
							mirror = false,
							prompt_position = "top",
							preview_cutoff = 120,
							preview_width = 0.5,
						},
					},
					file_sorter = require("telescope.sorters").get_fuzzy_file,
					file_ignore_patterns = {
						"node_modules/*",
						".git/*",
					},
					generic_sorter = require("telescope.sorters").get_generic_fuzzy_sorter,
					path_display = {},
					winblend = 0,
					border = {},
					borderchars = {
						{ "─", "│", "─", "│", "┌", "┐", "┘", "└" },
						prompt = { "─", "│", " ", "│", "┌", "┬", "│", "│" },
						results = { "─", "│", "─", "│", "├", "┤", "┴", "└" },
						preview = { "─", "│", "─", " ", "─", "┐", "┘", "─" },
					},
					color_devicons = true,
					use_less = true,
					scroll_strategy = "cycle",
					set_env = { ["COLORTERM"] = "truecolor" },
					buffer_previewer_maker = require("telescope.previewers").buffer_previewer_maker,
					mappings = {
						n = { ["<C-t>"] = action_layout.toggle_preview },
						i = {
							["<C-t>"] = action_layout.toggle_preview,
							["<C-x>"] = false,
							["<C-s>"] = actions.select_horizontal,
							["<Tab>"] = actions.toggle_selection + actions.move_selection_next,
							["<C-q>"] = actions.send_selected_to_qflist,
							["<CR>"] = actions.select_default + actions.center,
							["<C-g>"] = custom_actions.multi_selection_open,
						},
					},
					history = { path = "~/.local/share/nvim/databases/telescope_history.sqlite3", limit = 100 },
				},
				pickers = {
					find_files = {
						find_command = { "fd", "--type", "file", "--strip-cwd-prefix", "--hidden" },
					},
				},
				extensions = {
					frecency = {
						ignore_patterns = {
							"*.git/*",
							"*/tmp/*",
							"*/node_modules/*",
						},
						db_safe_mode = false,
					},
				},
			})

			local function join_uniq(tbl, tbl2)
				local res = {}
				local hash = {}
				for _, v1 in ipairs(tbl) do
					res[#res + 1] = v1
					hash[v1] = true
				end

				for _, v in pairs(tbl2) do
					if not hash[v] then
						table.insert(res, v)
					end
				end
				return res
			end

			local function filter_by_cwd_paths(tbl, cwd)
				local res = {}
				local hash = {}
				for _, v in ipairs(tbl) do
					if v:find(cwd, 1, true) then
						local v1 = Path:new(v):normalize(cwd)
						if not hash[v1] then
							res[#res + 1] = v1
							hash[v1] = true
						end
					end
				end
				return res
			end

			local function requiref(module)
				require(module)
			end

			telescope_builtin.my_mru = function(opts)
				local get_mru = function(options)
					local res = pcall(requiref, "telescope._extensions.frecency")
					if not res then
						return vim.tbl_filter(function(val)
							return 0 ~= vim.fn.filereadable(val)
						end, vim.v.oldfiles)
					else
						local db_client = require("telescope._extensions.frecency.db_client")
						db_client.init()
						-- too slow
						-- local tbl = db_client.get_file_scores(opts, vim.fn.getcwd())
						local tbl = db_client.get_file_scores(options)
						local get_filename_table = function(table)
							local result = {}
							for _, v in pairs(table) do
								result[#result + 1] = v["filename"]
							end
							return result
						end
						return get_filename_table(tbl)
					end
				end
				local results_mru = get_mru(opts)
				local results_mru_cur = filter_by_cwd_paths(results_mru, vim.loop.cwd())

				local show_untracked = utils.get_default(opts.show_untracked, true)
				local recurse_submodules = utils.get_default(opts.recurse_submodules, false)
				if show_untracked and recurse_submodules then
					error("Git does not suppurt both --others and --recurse-submodules")
				end
				local cmd = {
					"git",
					"ls-files",
					"--exclude-standard",
					"--cached",
					show_untracked and "--others" or nil,
					recurse_submodules and "--recurse-submodules" or nil,
				}
				local results_git = utils.get_os_command_output(cmd)

				local results = join_uniq(results_mru_cur, results_git)

				pickers
					.new(opts, {
						prompt_title = "MRU",
						finder = finders.new_table({
							results = results,
							entry_maker = opts.entry_maker or make_entry.gen_from_file(opts),
						}),
						-- default_text = vim.fn.getcwd(),
						sorter = conf.file_sorter(opts),
						previewkr = conf.file_previewer(opts),
					})
					:find()
			end

			telescope_builtin.grep_prompt = function(opts)
				opts.search = vim.fn.input("Grep String > ")
				telescope_builtin.my_grep(opts)
			end

			telescope_builtin.my_grep = function(opts)
				require("telescope.builtin").grep_string({
					opts = opts,
					prompt_title = "grep_string: " .. opts.search,
					search = opts.search,
				})
			end

			telescope_builtin.my_grep_in_dir = function(opts)
				opts.search = vim.fn.input("Grep String > ")
				opts.search_dirs = {}
				opts.search_dirs[1] = vim.fn.input("Target Directory > ")
				require("telescope.builtin").grep_string({
					opts = opts,
					prompt_title = "grep_string(dir): " .. opts.search,
					search = opts.search,
					search_dirs = opts.search_dirs,
				})
			end

			telescope_builtin.memo = function(opts)
				require("telescope.builtin").find_files({
					opts = opts,
					prompt_title = "MemoList",
					find_command = { "find", vim.g.memolist_path, "-type", "f", "-exec", "ls", "-1ta", "{}", "+" },
				})
			end
		end,
	},

	-- status line
	{
		"nvim-lualine/lualine.nvim",
		config = function()
			local lualine = require("lualine")
			local lualine_require = require("lualine_require")
			local utils = require("lualine.utils.utils")

			local is_available_gps = function()
				local ok, gps = pcall(require, "nvim-gps")
				if not ok then
					return false
				end
				return gps.is_available()
			end

			local is_blame_text_available = function()
				local ok, gitblame = pcall(require, "gitblame")
				if not ok then
					return false
				end

				local availability = gitblame.is_blame_text_available()
				if not availability or (gitblame.get_current_blame_text() == "  Not Committed Yet") then
					return false
				end
				return true
			end

			local format_filetype = function(buf_ft)
				local ft_table = {}
				ft_table["cpp"] = "C++"
				ft_table["typescript"] = "TypeScript"
				ft_table["javascript"] = "JavaScript"
				ft_table["typescriptreact"] = "TypeScript React"
				ft_table["javascriptreact"] = "JavaScript React"
				ft_table["json"] = "JSON"
				ft_table["jsonc"] = "JSON with Comments"
				ft_table["html"] = "HTML"
				ft_table["css"] = "CSS"
				ft_table["scss"] = "SCSS"
				ft_table["php"] = "PHP"
				ft_table["sql"] = "SQL"
				ft_table["ignore"] = "gitignore"
				ft_table["editorconfig"] = "EditorConfig"
				ft_table["git-commit"] = "Git Commit Message"
				ft_table["git-rebase"] = "Git Rebase Message"
				ft_table["dotenv"] = "Environment Variables"
				ft_table["gomod"] = "Go Module file"
				ft_table["proto"] = "Protocol Buffers"
				ft_table["sh"] = "Shell Script"
				ft_table["yaml"] = "YAML"
				ft_table["toml"] = "TOML"
				ft_table["vim"] = "Vim Script"
				ft_table["sshconfig"] = "SSH Config"

				local ft = ""
				if ft_table[buf_ft] ~= nil then
					ft = ft_table[buf_ft]
				elseif buf_ft == "" then
					ft = "Plain Text"
				else
					ft = string.gsub(buf_ft, "^%l", string.upper)
				end

				if buf_ft ~= "" then
					local clients = vim.lsp.get_active_clients()
					if next(clients) ~= nil then
						for _, client in ipairs(clients) do
							if client.name ~= "null-ls" then
								local filetypes = client.config.filetypes
								if filetypes and vim.fn.index(filetypes, buf_ft) ~= -1 then
									return string.format("%s", ft)
								end
							end
						end
					end
				end
				return string.format(" %s", ft)
			end

			local indent = function()
				local tabstop = vim.o.tabstop
				if vim.o.expandtab then
					return string.format("Spaces:%s", tabstop)
				else
					return string.format("Tab Size:%s", tabstop)
				end
			end

			local sections_1 = {
				lualine_a = {
					{
						"mode",
						fmt = function()
							return ""
						end,
					},
				},
				lualine_b = {
					{ "branch", icon = "" },
					{
						"diagnostics",
						sections = { "error", "warn" },
						colored = false,
						always_visible = true,
					},
				},
				lualine_c = {},
				lualine_x = {
					{
						'require("gitblame").get_current_blame_text()',
						cond = is_blame_text_available,
					},
					{
						"location",
						fmt = function()
							return " %l  %v"
						end,
					},
					{ indent },
					{ "encoding", fmt = string.upper, icon = "" },
					{
						"fileformat",
						fmt = function(icon)
							if icon == "" then
								return "LF"
							elseif icon == "" then
								return "CRLF"
							elseif icon == "" then
								return "CR"
							else
								return icon
							end
						end,
					},
					{
						"filetype",
						icons_enabled = false,
						fmt = format_filetype,
					},
				},
				lualine_y = {},
				lualine_z = {},
			}

			local sections_2 = {
				lualine_a = { { "mode" } },
				lualine_b = {},
				lualine_c = {},
				lualine_x = { "encoding", "fileformat", "filetype" },
				lualine_y = { "filesize", "progress" },
				lualine_z = { { "location" } },
			}

			vim.keymap.set("n", "!", function()
				local modules = lualine_require.lazy_require({ config_module = "lualine.config" })

				local current_config = modules.config_module.get_config()
				if vim.inspect(current_config.sections) == vim.inspect(sections_1) then
					current_config.sections = utils.deepcopy(sections_2)
				else
					current_config.sections = utils.deepcopy(sections_1)
				end
				lualine.setup(current_config)
			end, { noremap = true, silent = true })

			lualine.setup({
				options = {
					icon_enabled = true,
					theme = "catppuccin",
					section_separators = "",
					component_separators = "",
				},
				sections = sections_1,
				extensions = { "quickfix" },
			})
		end,
	},

	-- git
	{
		"lewis6991/gitsigns.nvim",
		event = "VimEnter",
		config = function()
			require("gitsigns").setup()
		end,
	},
	{
		"f-person/git-blame.nvim",
		event = "VimEnter",
		config = function()
			vim.g.gitblame_display_virtual_text = 0
			vim.g.gitblame_date_format = "%r"
			vim.g.gitblame_message_template = "<author>, <date>"
			vim.g.gitblame_ignored_filetypes = { "neo-tree", "SidebarNvim", "toggleterm" }
		end,
	},

	-- brackets
	{
		"andymass/vim-matchup",
		event = "VimEnter",
		config = function()
			vim.g.matchup_matchparen_offscreen = { method = "popup" }
		end,
	},
	{
		"hrsh7th/nvim-insx",
		event = "InsertEnter",
		config = function()
			require("insx.preset.standard").setup()
		end,
	},

	-- UI
	{
		"folke/noice.nvim",
		event = "VeryLazy",
		dependencies = "rcarriga/nvim-notify",
		config = function()
			require("noice").setup({
				lsp = {
					-- override markdown rendering so that **cmp** and other plugins use **Treesitter**
					override = {
						["vim.lsp.util.convert_input_to_markdown_lines"] = true,
						["vim.lsp.util.stylize_markdown"] = true,
						["cmp.entry.get_documentation"] = true,
					},
				},
				-- you can enable a preset for easier configuration
				presets = {
					bottom_search = true, -- use a classic bottom cmdline for search
					command_palette = true, -- position the cmdline and popupmenu together
					long_message_to_split = true, -- long messages will be sent to a split
					inc_rename = false, -- enables an input dialog for inc-rename.nvim
					lsp_doc_border = false, -- add a border to hover docs and signature help
				},
			})
		end,
	},

	-- syntax
	{
		"norcalli/nvim-colorizer.lua",
		config = function()
			require("colorizer").setup()
		end,
	},
	{
		"folke/todo-comments.nvim",
		config = function()
			require("todo-comments").setup({})
		end,
	},

	-- scroll bar
	{
		"petertriho/nvim-scrollbar",
		dependencies = "kevinhwang91/nvim-hlslens",
		config = function()
			require("scrollbar").setup({
				show = true,
				set_highlights = true,
				handle = {
					text = " ",
					color = "#3F4A5A",
					cterm = nil,
					highlight = "CursorColumn",
					hide_if_all_visible = true, -- Hides handle if all lines are visible
				},
				marks = {
					Search = {
						text = { "-", "=" },
						priority = 0,
						color = nil,
						cterm = nil,
						highlight = "Search",
					},
					Error = {
						text = { "-", "=" },
						priority = 1,
						color = nil,
						cterm = nil,
						highlight = "DiagnosticVirtualTextError",
					},
					Warn = {
						text = { "-", "=" },
						priority = 2,
						color = nil,
						cterm = nil,
						highlight = "DiagnosticVirtualTextWarn",
					},
					Info = {
						text = { "-", "=" },
						priority = 3,
						color = nil,
						cterm = nil,
						highlight = "DiagnosticVirtualTextInfo",
					},
					Hint = {
						text = { "-", "=" },
						priority = 4,
						color = nil,
						cterm = nil,
						highlight = "DiagnosticVirtualTextHint",
					},
					Misc = {
						text = { "-", "=" },
						priority = 5,
						color = nil,
						cterm = nil,
						highlight = "Normal",
					},
				},
				excluded_buftypes = {
					"terminal",
				},
				excluded_filetypes = {
					"prompt",
					"TelescopePrompt",
				},
				autocmd = {
					render = {
						"BufWinEnter",
						"TabEnter",
						"TermEnter",
						"WinEnter",
						"CmdwinLeave",
						-- "TextChanged",
						"VimResized",
						"WinScrolled",
					},
				},
				handlers = {
					diagnostic = true,
					search = true, -- Requires hlslens to be loaded, will run require("scrollbar.handlers.search").setup() for you
				},
			})
		end,
	},

	-- move
	{
		"folke/flash.nvim",
		event = "VeryLazy",
		keys = {
			{
				"f",
				mode = { "n", "x", "o" },
				function()
					require("flash").jump({
						search = { forward = true, wrap = false, multi_window = false },
					})
				end,
				desc = "Flash Forward",
			},
			{
				"F",
				mode = { "n", "x", "o" },
				function()
					require("flash").jump({
						search = { forward = false, wrap = false, multi_window = false },
					})
				end,
				desc = "Flash Backward",
			},
		},
	},

	-- join
	{
		"AckslD/nvim-trevJ.lua",
		config = function()
			require("trevj").setup()

			vim.keymap.set("v", "J", function()
				require("trevj").format_at_cursor()
			end, { noremap = true, silent = true })
		end,
	},

	-- manual
	{
		"folke/which-key.nvim",
		event = "VeryLazy",
		init = function()
			vim.o.timeout = true
			vim.o.timeoutlen = 300
		end,
		config = function()
			require("which-key").setup({
				plugins = {
					marks = false,
					registers = false,
					presets = {
						operators = false,
						motions = false,
						text_objects = false,
						windows = false,
						nav = false,
						z = false,
						g = false,
					},
				},
				icons = {
					breadcrumb = "»",
					separator = "➜",
					group = "+",
				},
				window = {
					border = "none",
					position = "bottom",
					margin = { 1, 0, 1, 0 },
					padding = { 2, 2, 2, 2 },
				},
				layout = {
					height = { min = 4, max = 25 },
					width = { min = 20, max = 50 },
					spacing = 3,
				},
				hidden = { "<silent>", "<cmd>", "<Cmd>", "<CR>", "call", "lua", "^:", "^ " },
				show_help = true,
				triggers = { "<Leader>" },
			})
		end,
	},

	-- coding
	{ "zsugabubus/crazy8.nvim", event = { "BufNewFile", "BufReadPost" } },
	{
		"lukas-reineke/indent-blankline.nvim",
		event = "VimEnter",
		config = function()
			require("indent_blankline").setup({
				show_current_context = true,
				buftype_exclude = { "terminal" },
				filetype_exclude = {
					"help",
					"neo-tree",
					"packer",
					"log",
					"lspsagafinder",
					"lspinfo",
					"toggleterm",
					"alpha",
				},
			})

			vim.api.nvim_clear_autocmds({
				event = { "TextChanged", "TextChangedI" },
				group = "IndentBlanklineAutogroup",
			})
		end,
	},

	-- comment
	{
		"numToStr/Comment.nvim",
		event = "VimEnter",
		config = function()
			require("Comment").setup({
				mappings = {
					basic = true,
					extra = false,
					extended = false,
				},
				pre_hook = function()
					return require("ts_context_commentstring.internal").calculate_commentstring({
						location = require("ts_context_commentstring.utils").get_cursor_location(),
					})
				end,
			})
		end,
	},

	-- format
	{ "gpanders/editorconfig.nvim", event = "VimEnter" },

	-- sql
	{ "alcesleo/vim-uppercase-sql", event = "VimEnter" },

	-- csv
	{
		"chen244/csv-tools.lua",
		ft = { "csv" },
		config = function()
			require("csvtools").setup({
				before = 10,
				after = 10,
				clearafter = false,
				showoverflow = false,
				titelflow = true,
			})
		end,
	},

	-- log
	{ "MTDL9/vim-log-highlighting", ft = { "log" } },
})
